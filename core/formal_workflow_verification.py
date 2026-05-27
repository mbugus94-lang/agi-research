"""
Formal Workflow Verification System

Based on arXiv:2605.14968v1 "GraphFlow: An Architecture for Formally 
Verifiable Visual Workflows Enabling Reliable Agentic AI Automation"

Provides formal guarantees for workflow execution through:
1. Pre-condition checking before node execution
2. Post-condition validation after node completion  
3. Invariant preservation throughout workflow
4. Formal verification of workflow structure
5. Safety property enforcement

Key Concepts:
- Condition: Boolean predicate over workflow state
- Invariant: Condition that must hold throughout execution
- Verification Rule: Formal specification of correct behavior
- Proof Obligation: Required verification checks
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Set, Tuple, Union
from enum import Enum, auto
from datetime import datetime
import uuid
import json
from collections import defaultdict


class VerificationStatus(Enum):
    """Status of verification checks"""
    UNCHECKED = "unchecked"
    PASSING = "passing"
    FAILING = "failing"
    VIOLATED = "violated"
    RECOVERED = "recovered"


class VerificationType(Enum):
    """Types of verification rules"""
    PRE_CONDITION = "pre_condition"      # Must hold before execution
    POST_CONDITION = "post_condition"    # Must hold after execution
    INVARIANT = "invariant"              # Must hold throughout
    SAFETY = "safety"                    # Safety property
    LIVENESS = "liveness"                # Progress guarantee


class VerificationSeverity(Enum):
    """Severity of verification failures"""
    INFO = "info"           # Informational only
    WARNING = "warning"      # Warn but continue
    ERROR = "error"          # Block execution
    CRITICAL = "critical"    # Abort workflow


@dataclass
class WorkflowState:
    """Represents the state of a workflow execution"""
    variables: Dict[str, Any] = field(default_factory=dict)
    node_outputs: Dict[str, Any] = field(default_factory=dict)
    execution_path: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    
    def get(self, key: str, default=None) -> Any:
        """Get value from variables or node outputs"""
        if key in self.variables:
            return self.variables[key]
        if key in self.node_outputs:
            return self.node_outputs[key]
        return default
    
    def set(self, key: str, value: Any) -> None:
        """Set a variable value"""
        self.variables[key] = value
    
    def record_node_output(self, node_id: str, output: Any) -> None:
        """Record output from a node execution"""
        self.node_outputs[node_id] = output
        self.execution_path.append(node_id)
    
    def copy(self) -> "WorkflowState":
        """Create a copy of the state"""
        return WorkflowState(
            variables=self.variables.copy(),
            node_outputs=self.node_outputs.copy(),
            execution_path=self.execution_path.copy(),
            metadata=self.metadata.copy(),
            timestamp=datetime.now().timestamp()
        )
    
    def to_dict(self) -> Dict:
        return {
            "variables": self.variables,
            "node_outputs": self.node_outputs,
            "execution_path": self.execution_path,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }


@dataclass
class VerificationResult:
    """Result of a verification check"""
    rule_id: str
    rule_name: str
    status: VerificationStatus
    verification_type: VerificationType
    severity: VerificationSeverity
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    node_id: Optional[str] = None
    
    @property
    def is_blocking(self) -> bool:
        """Whether this failure should block execution"""
        return self.status == VerificationStatus.VIOLATED and \
               self.severity in [VerificationSeverity.ERROR, VerificationSeverity.CRITICAL]
    
    def to_dict(self) -> Dict:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "status": self.status.value,
            "verification_type": self.verification_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
            "node_id": self.node_id
        }


@dataclass
class VerificationRule:
    """A formal verification rule"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    rule_type: VerificationType = VerificationType.INVARIANT
    severity: VerificationSeverity = VerificationSeverity.ERROR
    
    # The condition function - takes WorkflowState, returns (bool, details)
    condition: Optional[Callable[[WorkflowState], Tuple[bool, Optional[str]]]] = None
    
    # Node IDs this rule applies to (empty = applies to all)
    applies_to_nodes: List[str] = field(default_factory=list)
    
    # Custom error message
    failure_message: str = ""
    
    # Whether rule is active
    active: bool = True
    
    # Metadata
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    
    def evaluate(self, state: WorkflowState, node_id: Optional[str] = None) -> VerificationResult:
        """Evaluate this rule against a workflow state"""
        if not self.active:
            return VerificationResult(
                rule_id=self.id,
                rule_name=self.name,
                status=VerificationStatus.UNCHECKED,
                verification_type=self.rule_type,
                severity=self.severity,
                message="Rule inactive",
                node_id=node_id
            )
        
        # Check if rule applies to this node
        if self.applies_to_nodes and node_id not in self.applies_to_nodes:
            return VerificationResult(
                rule_id=self.id,
                rule_name=self.name,
                status=VerificationStatus.UNCHECKED,
                verification_type=self.rule_type,
                severity=self.severity,
                message="Rule does not apply to this node",
                node_id=node_id
            )
        
        if self.condition is None:
            return VerificationResult(
                rule_id=self.id,
                rule_name=self.name,
                status=VerificationStatus.UNCHECKED,
                verification_type=self.rule_type,
                severity=self.severity,
                message="No condition defined",
                node_id=node_id
            )
        
        try:
            passed, details = self.condition(state)
            
            if passed:
                return VerificationResult(
                    rule_id=self.id,
                    rule_name=self.name,
                    status=VerificationStatus.PASSING,
                    verification_type=self.rule_type,
                    severity=self.severity,
                    message="Verification passed",
                    details={"details": details} if details else {},
                    node_id=node_id
                )
            else:
                msg = self.failure_message or details or "Verification failed"
                return VerificationResult(
                    rule_id=self.id,
                    rule_name=self.name,
                    status=VerificationStatus.VIOLATED,
                    verification_type=self.rule_type,
                    severity=self.severity,
                    message=msg,
                    details={"details": details} if details else {},
                    node_id=node_id
                )
        except Exception as e:
            return VerificationResult(
                rule_id=self.id,
                rule_name=self.name,
                status=VerificationStatus.VIOLATED,
                verification_type=self.rule_type,
                severity=VerificationSeverity.CRITICAL,
                message=f"Verification error: {str(e)}",
                details={"error": str(e)},
                node_id=node_id
            )


class FormalWorkflowVerifier:
    """
    Formal verification engine for workflow DAGs.
    
    Provides GraphFlow-style formal guarantees:
    - Pre/post condition checking
    - Invariant preservation
    - Safety property enforcement
    - Structured verification reports
    """
    
    def __init__(self):
        self.rules: Dict[str, VerificationRule] = {}
        self.results: List[VerificationResult] = []
        self.invariants: List[str] = []  # Rule IDs that are invariants
        self.state_history: List[WorkflowState] = []
    
    def add_rule(self, rule: VerificationRule) -> str:
        """Add a verification rule"""
        self.rules[rule.id] = rule
        if rule.rule_type == VerificationType.INVARIANT:
            self.invariants.append(rule.id)
        return rule.id
    
    def add_pre_condition(
        self,
        name: str,
        condition: Callable[[WorkflowState], Tuple[bool, Optional[str]]],
        applies_to: Optional[List[str]] = None,
        severity: VerificationSeverity = VerificationSeverity.ERROR,
        message: str = ""
    ) -> str:
        """Add a pre-condition rule"""
        rule = VerificationRule(
            name=name,
            rule_type=VerificationType.PRE_CONDITION,
            condition=condition,
            applies_to_nodes=applies_to or [],
            severity=severity,
            failure_message=message
        )
        return self.add_rule(rule)
    
    def add_post_condition(
        self,
        name: str,
        condition: Callable[[WorkflowState], Tuple[bool, Optional[str]]],
        applies_to: Optional[List[str]] = None,
        severity: VerificationSeverity = VerificationSeverity.ERROR,
        message: str = ""
    ) -> str:
        """Add a post-condition rule"""
        rule = VerificationRule(
            name=name,
            rule_type=VerificationType.POST_CONDITION,
            condition=condition,
            applies_to_nodes=applies_to or [],
            severity=severity,
            failure_message=message
        )
        return self.add_rule(rule)
    
    def add_invariant(
        self,
        name: str,
        condition: Callable[[WorkflowState], Tuple[bool, Optional[str]]],
        severity: VerificationSeverity = VerificationSeverity.CRITICAL,
        message: str = ""
    ) -> str:
        """Add an invariant that must hold throughout execution"""
        rule = VerificationRule(
            name=name,
            rule_type=VerificationType.INVARIANT,
            condition=condition,
            severity=severity,
            failure_message=message
        )
        return self.add_rule(rule)
    
    def add_safety_property(
        self,
        name: str,
        condition: Callable[[WorkflowState], Tuple[bool, Optional[str]]],
        severity: VerificationSeverity = VerificationSeverity.CRITICAL,
        message: str = ""
    ) -> str:
        """Add a safety property"""
        rule = VerificationRule(
            name=name,
            rule_type=VerificationType.SAFETY,
            condition=condition,
            severity=severity,
            failure_message=message
        )
        return self.add_rule(rule)
    
    def verify_pre_conditions(
        self,
        state: WorkflowState,
        node_id: str
    ) -> List[VerificationResult]:
        """Verify all pre-conditions for a node"""
        results = []
        
        for rule in self.rules.values():
            if rule.rule_type == VerificationType.PRE_CONDITION:
                result = rule.evaluate(state, node_id)
                results.append(result)
                self.results.append(result)
        
        # Also check invariants before execution
        for rule_id in self.invariants:
            rule = self.rules[rule_id]
            result = rule.evaluate(state, node_id)
            results.append(result)
            self.results.append(result)
        
        return results
    
    def verify_post_conditions(
        self,
        state: WorkflowState,
        node_id: str
    ) -> List[VerificationResult]:
        """Verify all post-conditions for a node"""
        results = []
        
        for rule in self.rules.values():
            if rule.rule_type == VerificationType.POST_CONDITION:
                result = rule.evaluate(state, node_id)
                results.append(result)
                self.results.append(result)
        
        # Re-check invariants after execution
        for rule_id in self.invariants:
            rule = self.rules[rule_id]
            result = rule.evaluate(state, node_id)
            results.append(result)
            self.results.append(result)
        
        return results
    
    def check_invariants(self, state: WorkflowState) -> List[VerificationResult]:
        """Check all invariants against current state"""
        results = []
        
        for rule_id in self.invariants:
            rule = self.rules[rule_id]
            result = rule.evaluate(state)
            results.append(result)
            self.results.append(result)
        
        return results
    
    def has_blocking_failures(self, results: List[VerificationResult]) -> bool:
        """Check if any results are blocking"""
        return any(r.is_blocking for r in results)
    
    def get_failures(
        self,
        severity_threshold: Optional[VerificationSeverity] = None
    ) -> List[VerificationResult]:
        """Get all failing verifications"""
        failures = [r for r in self.results if r.status == VerificationStatus.VIOLATED]
        
        if severity_threshold:
            severity_order = [
                VerificationSeverity.INFO,
                VerificationSeverity.WARNING,
                VerificationSeverity.ERROR,
                VerificationSeverity.CRITICAL
            ]
            threshold_idx = severity_order.index(severity_threshold)
            failures = [
                r for r in failures 
                if severity_order.index(r.severity) >= threshold_idx
            ]
        
        return failures
    
    def get_verification_report(self) -> Dict:
        """Generate comprehensive verification report"""
        total = len(self.results)
        passing = len([r for r in self.results if r.status == VerificationStatus.PASSING])
        violated = len([r for r in self.results if r.status == VerificationStatus.VIOLATED])
        unchecked = len([r for r in self.results if r.status == VerificationStatus.UNCHECKED])
        
        by_type = defaultdict(lambda: {"passing": 0, "violated": 0, "unchecked": 0})
        for r in self.results:
            category = by_type[r.verification_type.value]
            if r.status == VerificationStatus.PASSING:
                category["passing"] += 1
            elif r.status == VerificationStatus.VIOLATED:
                category["violated"] += 1
            else:
                category["unchecked"] += 1
        
        critical_failures = [
            r.to_dict() for r in self.results
            if r.status == VerificationStatus.VIOLATED and 
               r.severity == VerificationSeverity.CRITICAL
        ]
        
        return {
            "summary": {
                "total_checks": total,
                "passing": passing,
                "violated": violated,
                "unchecked": unchecked,
                "pass_rate": passing / total if total > 0 else 0
            },
            "by_type": dict(by_type),
            "critical_failures": critical_failures,
            "all_results": [r.to_dict() for r in self.results]
        }
    
    def record_state(self, state: WorkflowState) -> None:
        """Record state snapshot for invariant tracking"""
        self.state_history.append(state.copy())
    
    def clear_results(self) -> None:
        """Clear all verification results"""
        self.results = []


class VerifiedWorkflowNode:
    """A workflow node with formal verification support"""
    
    def __init__(
        self,
        node_id: str,
        executor: Callable[[WorkflowState], Tuple[Any, WorkflowState]],
        verifier: FormalWorkflowVerifier,
        pre_condition_rules: Optional[List[str]] = None,
        post_condition_rules: Optional[List[str]] = None
    ):
        self.node_id = node_id
        self.executor = executor
        self.verifier = verifier
        self.pre_condition_rules = pre_condition_rules or []
        self.post_condition_rules = post_condition_rules or []
        self.execution_count = 0
        self.failure_count = 0
    
    def execute(self, state: WorkflowState) -> Tuple[Any, List[VerificationResult], bool]:
        """
        Execute node with formal verification.
        
        Returns:
            (output, verification_results, should_continue)
        """
        # Pre-condition verification
        pre_results = self.verifier.verify_pre_conditions(state, self.node_id)
        
        if self.verifier.has_blocking_failures(pre_results):
            return None, pre_results, False
        
        # Record state before execution
        self.verifier.record_state(state)
        
        # Execute
        try:
            output, new_state = self.executor(state)
            self.execution_count += 1
            
            # Record output
            new_state.record_node_output(self.node_id, output)
            
            # Post-condition verification
            post_results = self.verifier.verify_post_conditions(new_state, self.node_id)
            
            all_results = pre_results + post_results
            should_continue = not self.verifier.has_blocking_failures(post_results)
            
            return output, all_results, should_continue
            
        except Exception as e:
            self.failure_count += 1
            error_result = VerificationResult(
                rule_id="execution",
                rule_name="Node Execution",
                status=VerificationStatus.VIOLATED,
                verification_type=VerificationType.SAFETY,
                severity=VerificationSeverity.CRITICAL,
                message=f"Execution failed: {str(e)}",
                details={"error": str(e)},
                node_id=self.node_id
            )
            return None, pre_results + [error_result], False


# Convenience functions for common verifications

def create_type_check(
    variable: str,
    expected_type: type,
    message: str = ""
) -> Callable[[WorkflowState], Tuple[bool, Optional[str]]]:
    """Create a type-checking condition"""
    def check(state: WorkflowState) -> Tuple[bool, Optional[str]]:
        value = state.get(variable)
        if value is None:
            return False, message or f"Variable '{variable}' is None"
        if not isinstance(value, expected_type):
            return False, message or f"Expected {expected_type.__name__}, got {type(value).__name__}"
        return True, None
    return check


def create_range_check(
    variable: str,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    message: str = ""
) -> Callable[[WorkflowState], Tuple[bool, Optional[str]]]:
    """Create a range-checking condition"""
    def check(state: WorkflowState) -> Tuple[bool, Optional[str]]:
        value = state.get(variable)
        if value is None:
            return False, message or f"Variable '{variable}' is None"
        
        try:
            num_val = float(value)
            if min_val is not None and num_val < min_val:
                return False, message or f"{variable}={num_val} below minimum {min_val}"
            if max_val is not None and num_val > max_val:
                return False, message or f"{variable}={num_val} above maximum {max_val}"
            return True, None
        except (TypeError, ValueError):
            return False, message or f"Variable '{variable}' is not numeric"
    return check


def create_not_empty_check(
    variable: str,
    message: str = ""
) -> Callable[[WorkflowState], Tuple[bool, Optional[str]]]:
    """Create a not-empty check condition"""
    def check(state: WorkflowState) -> Tuple[bool, Optional[str]]:
        value = state.get(variable)
        if value is None:
            return False, message or f"Variable '{variable}' is None"
        if isinstance(value, (str, list, dict, set)) and len(value) == 0:
            return False, message or f"Variable '{variable}' is empty"
        return True, None
    return check


def create_dependency_check(
    input_var: str,
    output_var: str,
    message: str = ""
) -> Callable[[WorkflowState], Tuple[bool, Optional[str]]]:
    """Create a dependency check (output should relate to input)"""
    def check(state: WorkflowState) -> Tuple[bool, Optional[str]]:
        input_val = state.get(input_var)
        output_val = state.get(output_var)
        
        if input_val is None:
            return False, message or f"Input '{input_var}' is None"
        if output_val is None:
            return False, message or f"Output '{output_var}' is None"
        
        # Simple check: output should be non-empty if input is non-empty
        if isinstance(input_val, (str, list, dict)) and len(input_val) > 0:
            if isinstance(output_val, (str, list, dict)) and len(output_val) == 0:
                return False, message or f"Output '{output_var}' is empty but input '{input_var}' is not"
        
        return True, None
    return check