"""
Safety Circuit Breaker - Critical Protection for Autonomous Agents

Based on May 2026 research:
- Claude AI incident: Rogue agent deleted production database in 9 seconds
- Global cybersecurity warnings (USA, UK, Australia): "Every component widens attack surface"
- Constitutional governance: Safety-first self-modification requirements
- Zero-Trust security: Verify every action, especially self-modifications

Core Principle: All potentially dangerous operations MUST pass through
circuit breaker validation with human-in-the-loop for irreversible actions.
"""

import json
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Callable, Set
from collections import defaultdict
import re


class RiskLevel(Enum):
    """Risk classification for operations."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    
    def __lt__(self, other):
        if isinstance(other, RiskLevel):
            return self.value < other.value
        return NotImplemented
    
    def __le__(self, other):
        if isinstance(other, RiskLevel):
            return self.value <= other.value
        return NotImplemented
    
    def __gt__(self, other):
        if isinstance(other, RiskLevel):
            return self.value > other.value
        return NotImplemented
    
    def __ge__(self, other):
        if isinstance(other, RiskLevel):
            return self.value >= other.value
        return NotImplemented


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Failure threshold exceeded, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class ActionCategory(Enum):
    """Categories of agent actions for risk assessment."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    MODIFY_SELF = "modify_self"
    EXTERNAL_API = "external_api"
    FILE_SYSTEM = "file_system"
    DATABASE = "database"
    NETWORK = "network"


@dataclass
class SafetyPolicy:
    """Defines safety constraints for an action category."""
    category: ActionCategory
    max_daily_operations: int = 1000
    require_approval_above: RiskLevel = RiskLevel.HIGH
    allowed_paths: List[str] = field(default_factory=list)
    blocked_paths: List[str] = field(default_factory=lambda: [
        "/etc/passwd", "/etc/shadow", "/root/.ssh",
        ".env", "id_rsa", ".aws/credentials", ".kube/config"
    ])
    allowed_commands: List[str] = field(default_factory=list)
    blocked_commands: List[str] = field(default_factory=lambda: [
        "rm -rf /", "dd if=/dev/zero", "mkfs.", ":(){ :|:& };:"
    ])
    rate_limit_per_minute: int = 60


@dataclass
class OperationRecord:
    """Record of an operation for audit trail."""
    operation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    action_category: ActionCategory = ActionCategory.READ
    risk_level: RiskLevel = RiskLevel.LOW
    description: str = ""
    target: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    approved: bool = False
    approval_method: str = "auto"  # auto, policy, human_required, blocked
    execution_time_ms: float = 0.0
    result_status: str = "pending"  # pending, success, failure, blocked
    result_details: str = ""
    stack_trace: Optional[str] = None


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""
    total_requests: int = 0
    approved_requests: int = 0
    blocked_requests: int = 0
    failed_requests: int = 0
    policy_violations: int = 0
    high_risk_operations: int = 0
    last_failure_time: Optional[str] = None
    consecutive_failures: int = 0
    average_response_time_ms: float = 0.0


class SafetyCircuitBreaker:
    """
    Circuit breaker for agent safety - prevents catastrophic failures.
    
    Features:
    - Risk assessment for all operations
    - Policy-based approval routing
    - Rate limiting per category
    - Path/command blocklists
    - Audit logging for all decisions
    - Circuit state management (open/closed/half-open)
    - Self-modification review requirements
    
    Usage:
        cb = SafetyCircuitBreaker()
        
        # Register operation
        with cb.operation(ActionCategory.FILE_SYSTEM, "/workspace/data.txt") as op:
            op.risk_level = RiskLevel.MEDIUM
            op.description = "Write analysis results"
            if cb.check_operation(op):
                # Execute operation
                pass
    """
    
    def __init__(self, 
                 failure_threshold: int = 5,
                 recovery_timeout_seconds: int = 60,
                 enable_self_modification_review: bool = True):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.enable_self_modification_review = enable_self_modification_review
        
        # Circuit state
        self.state = CircuitState.CLOSED
        self.last_failure_time: Optional[float] = None
        
        # Policies
        self.policies: Dict[ActionCategory, SafetyPolicy] = {}
        self._init_default_policies()
        
        # Operation history
        self.operation_history: List[OperationRecord] = []
        self.pending_approvals: Dict[str, OperationRecord] = {}
        
        # Statistics
        self.stats = CircuitBreakerStats()
        
        # Custom validators
        self.validators: Dict[ActionCategory, List[Callable]] = defaultdict(list)
        
    def _init_default_policies(self):
        """Initialize default safety policies."""
        # Read operations - generally safe
        self.policies[ActionCategory.READ] = SafetyPolicy(
            category=ActionCategory.READ,
            require_approval_above=RiskLevel.CRITICAL,
            rate_limit_per_minute=1000
        )
        
        # Write operations - medium risk
        self.policies[ActionCategory.WRITE] = SafetyPolicy(
            category=ActionCategory.WRITE,
            require_approval_above=RiskLevel.HIGH,
            allowed_paths=["/home/workspace/", "/tmp/", "/var/tmp/"],
            rate_limit_per_minute=100
        )
        
        # Delete operations - high risk
        self.policies[ActionCategory.DELETE] = SafetyPolicy(
            category=ActionCategory.DELETE,
            require_approval_above=RiskLevel.MEDIUM,
            allowed_paths=["/home/workspace/", "/tmp/"],
            rate_limit_per_minute=10
        )
        
        # Self-modification - always critical
        self.policies[ActionCategory.MODIFY_SELF] = SafetyPolicy(
            category=ActionCategory.MODIFY_SELF,
            max_daily_operations=10,
            require_approval_above=RiskLevel.LOW,  # Everything requires approval
            rate_limit_per_minute=1
        )
        
        # Database operations
        self.policies[ActionCategory.DATABASE] = SafetyPolicy(
            category=ActionCategory.DATABASE,
            require_approval_above=RiskLevel.HIGH,
            rate_limit_per_minute=30
        )
        
        # External API calls
        self.policies[ActionCategory.EXTERNAL_API] = SafetyPolicy(
            category=ActionCategory.EXTERNAL_API,
            require_approval_above=RiskLevel.MEDIUM,
            rate_limit_per_minute=60
        )
        
        # File system operations
        self.policies[ActionCategory.FILE_SYSTEM] = SafetyPolicy(
            category=ActionCategory.FILE_SYSTEM,
            require_approval_above=RiskLevel.HIGH,
            allowed_paths=["/home/workspace/", "/tmp/"],
            rate_limit_per_minute=50
        )
        
        # Execute operations
        self.policies[ActionCategory.EXECUTE] = SafetyPolicy(
            category=ActionCategory.EXECUTE,
            require_approval_above=RiskLevel.MEDIUM,
            rate_limit_per_minute=10
        )
    
    def assess_risk(self, 
                   category: ActionCategory, 
                   target: str,
                   description: str = "",
                   parameters: Optional[Dict] = None) -> RiskLevel:
        """
        Assess risk level for an operation.
        
        Returns:
            RiskLevel based on category, target, and content analysis
        """
        params = parameters or {}
        
        # Critical: Self-modification is always high risk
        if category == ActionCategory.MODIFY_SELF:
            return RiskLevel.CRITICAL
        
        # Critical: Deletion of production data
        if category == ActionCategory.DELETE:
            if any(kw in target.lower() for kw in ["production", "prod", "main", "master"]):
                return RiskLevel.CRITICAL
            if any(kw in description.lower() for kw in ["database", "db", "drop", "truncate"]):
                return RiskLevel.CRITICAL
            return RiskLevel.HIGH
        
        # High: Database modifications
        if category == ActionCategory.DATABASE:
            if any(kw in description.lower() for kw in ["drop", "delete", "truncate", "alter"]):
                return RiskLevel.CRITICAL
            return RiskLevel.HIGH
        
        # High: File system operations outside allowed paths
        if category == ActionCategory.FILE_SYSTEM:
            policy = self.policies.get(category)
            if policy:
                is_allowed = any(
                    target.startswith(path) for path in policy.allowed_paths
                )
                if not is_allowed:
                    return RiskLevel.HIGH
            return RiskLevel.MEDIUM
        
        # Medium: External API calls with write operations
        if category == ActionCategory.EXTERNAL_API:
            if any(kw in description.lower() for kw in ["post", "put", "delete", "update"]):
                return RiskLevel.HIGH
            return RiskLevel.MEDIUM
        
        # Medium: Code execution
        if category == ActionCategory.EXECUTE:
            if any(kw in target.lower() for kw in self.policies[category].blocked_commands):
                return RiskLevel.CRITICAL
            return RiskLevel.MEDIUM
        
        # Low: Read operations
        if category == ActionCategory.READ:
            return RiskLevel.LOW
        
        return RiskLevel.MEDIUM
    
    def check_operation(self, record: OperationRecord) -> bool:
        """
        Check if operation should be allowed.
        
        Returns True if approved, False if blocked.
        """
        self.stats.total_requests += 1
        
        # Check circuit state
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                record.result_status = "blocked"
                record.result_details = "Circuit breaker is OPEN"
                record.approved = False
                self.operation_history.append(record)
                self.stats.blocked_requests += 1
                return False
        
        # Get policy
        policy = self.policies.get(record.action_category)
        if not policy:
            record.result_status = "blocked"
            record.result_details = "No policy defined for category"
            self.stats.blocked_requests += 1
            return False
        
        # Check rate limits
        if not self._check_rate_limit(record.action_category, policy):
            record.result_status = "blocked"
            record.result_details = "Rate limit exceeded"
            self.stats.blocked_requests += 1
            return False
        
        # Check blocklists
        if self._is_blocked(record):
            record.result_status = "blocked"
            record.result_details = "Operation matches blocklist"
            self.stats.policy_violations += 1
            self.operation_history.append(record)
            self._record_failure()
            return False
        
        # Check if approval required
        if record.risk_level.value >= policy.require_approval_above.value:
            if record.risk_level == RiskLevel.CRITICAL and self.enable_self_modification_review:
                record.approval_method = "human_required"
                self.pending_approvals[record.operation_id] = record
                record.result_status = "pending_approval"
                self.stats.high_risk_operations += 1
                return False  # Requires explicit human approval
            else:
                record.approval_method = "policy"
                record.approved = True
        else:
            record.approval_method = "auto"
            record.approved = True
        
        # Run custom validators
        for validator in self.validators.get(record.action_category, []):
            if not validator(record):
                record.result_status = "blocked"
                record.result_details = "Custom validator failed"
                self.stats.blocked_requests += 1
                return False
        
        record.result_status = "approved"
        self.operation_history.append(record)
        self.stats.approved_requests += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.stats.consecutive_failures = 0
        
        return True
    
    def _check_rate_limit(self, category: ActionCategory, policy: SafetyPolicy) -> bool:
        """Check if operation is within rate limit."""
        cutoff = datetime.now().timestamp() - 60  # Last minute
        recent_count = sum(
            1 for op in self.operation_history
            if op.action_category == category
            and datetime.fromisoformat(op.timestamp).timestamp() > cutoff
        )
        return recent_count < policy.rate_limit_per_minute
    
    def _is_blocked(self, record: OperationRecord) -> bool:
        """Check if operation matches blocklist."""
        policy = self.policies.get(record.action_category)
        if not policy:
            return False
        
        target = record.target.lower()
        
        # Check blocked paths
        for blocked in policy.blocked_paths:
            if blocked.lower() in target:
                return True
        
        # Check blocked commands
        for blocked in policy.blocked_commands:
            if blocked.lower() in target:
                return True
        
        return False
    
    def _record_failure(self):
        """Record a failure and potentially open circuit."""
        self.stats.consecutive_failures += 1
        self.stats.failed_requests += 1
        self.last_failure_time = datetime.now().timestamp()
        
        if self.stats.consecutive_failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try resetting."""
        if self.last_failure_time is None:
            return True
        elapsed = datetime.now().timestamp() - self.last_failure_time
        return elapsed >= self.recovery_timeout_seconds
    
    def approve_pending(self, operation_id: str) -> bool:
        """Explicitly approve a pending high-risk operation."""
        if operation_id not in self.pending_approvals:
            return False
        
        record = self.pending_approvals.pop(operation_id)
        record.approved = True
        record.result_status = "approved"
        record.approval_method = "human_approved"
        self.operation_history.append(record)
        self.stats.approved_requests += 1
        return True
    
    def reject_pending(self, operation_id: str, reason: str = "") -> bool:
        """Reject a pending high-risk operation."""
        if operation_id not in self.pending_approvals:
            return False
        
        record = self.pending_approvals.pop(operation_id)
        record.approved = False
        record.result_status = "rejected"
        record.result_details = reason or "Rejected by operator"
        self.operation_history.append(record)
        self.stats.blocked_requests += 1
        return True
    
    def get_audit_log(self, 
                     category: Optional[ActionCategory] = None,
                     risk_level: Optional[RiskLevel] = None,
                     limit: int = 100) -> List[OperationRecord]:
        """Get filtered audit log."""
        results = self.operation_history
        
        if category:
            results = [r for r in results if r.action_category == category]
        if risk_level:
            results = [r for r in results if r.risk_level == risk_level]
        
        return results[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "circuit_state": self.state.value,
            "total_requests": self.stats.total_requests,
            "approved_requests": self.stats.approved_requests,
            "blocked_requests": self.stats.blocked_requests,
            "failed_requests": self.stats.failed_requests,
            "policy_violations": self.stats.policy_violations,
            "high_risk_operations": self.stats.high_risk_operations,
            "pending_approvals": len(self.pending_approvals),
            "consecutive_failures": self.stats.consecutive_failures
        }
    
    def add_validator(self, 
                     category: ActionCategory, 
                     validator: Callable[[OperationRecord], bool]):
        """Add a custom validator for a category."""
        self.validators[category].append(validator)
    
    def reset_circuit(self):
        """Manually reset circuit to closed state."""
        self.state = CircuitState.CLOSED
        self.stats.consecutive_failures = 0
        self.last_failure_time = None


class SelfModificationGuard:
    """
    Specialized guard for self-modification operations.
    
    Based on Ouroboros BIBLE.md pattern and constitutional governance research.
    All self-modifications require:
    1. Risk assessment
    2. Change documentation
    3. Rollback plan
    4. Human approval for critical changes
    """
    
    def __init__(self, circuit_breaker: SafetyCircuitBreaker):
        self.cb = circuit_breaker
        self.modification_history: List[Dict] = []
        
    def propose_modification(self,
                            description: str,
                            target_file: str,
                            change_summary: str,
                            rollback_plan: str,
                            test_plan: str) -> Optional[str]:
        """
        Propose a self-modification.
        
        Returns operation_id if proposal created, None if blocked.
        """
        record = OperationRecord(
            action_category=ActionCategory.MODIFY_SELF,
            risk_level=RiskLevel.CRITICAL,
            description=description,
            target=target_file,
            parameters={
                "change_summary": change_summary,
                "rollback_plan": rollback_plan,
                "test_plan": test_plan,
                "proposed_at": datetime.now().isoformat()
            }
        )
        
        # Always requires human approval
        allowed = self.cb.check_operation(record)
        
        if not allowed and record.operation_id in self.cb.pending_approvals:
            # Proposal created, awaiting approval
            self.modification_history.append({
                "operation_id": record.operation_id,
                "description": description,
                "target": target_file,
                "status": "pending_approval",
                "proposed_at": datetime.now().isoformat()
            })
            return record.operation_id
        
        return None
    
    def get_pending_modifications(self) -> List[Dict]:
        """Get list of pending modification proposals."""
        return [
            mod for mod in self.modification_history
            if mod.get("status") == "pending_approval"
        ]
    
    def approve_modification(self, operation_id: str, reviewer: str = "") -> bool:
        """Approve a pending modification."""
        if self.cb.approve_pending(operation_id):
            for mod in self.modification_history:
                if mod.get("operation_id") == operation_id:
                    mod["status"] = "approved"
                    mod["approved_by"] = reviewer or "unknown"
                    mod["approved_at"] = datetime.now().isoformat()
                    return True
        return False
    
    def reject_modification(self, operation_id: str, reason: str = "") -> bool:
        """Reject a pending modification."""
        if self.cb.reject_pending(operation_id, reason):
            for mod in self.modification_history:
                if mod.get("operation_id") == operation_id:
                    mod["status"] = "rejected"
                    mod["rejection_reason"] = reason
                    mod["rejected_at"] = datetime.now().isoformat()
                    return True
        return False


def create_safety_circuit_breaker() -> SafetyCircuitBreaker:
    """Factory function with production-safe defaults."""
    return SafetyCircuitBreaker(
        failure_threshold=3,
        recovery_timeout_seconds=300,
        enable_self_modification_review=True
    )
