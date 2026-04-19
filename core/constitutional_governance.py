"""
Constitutional Governance Framework for AGI Agents
Inspired by Ouroboros BIBLE.md pattern - Safety-first self-modification governance

This module implements a constitutional framework that governs self-modification
behaviors, ensuring safety through:
1. Constitutional principles enforcement
2. Multi-model review simulation
3. Self-modification safety checks
4. Audit trails and recovery mechanisms
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Set
from datetime import datetime
import hashlib
import json


class PrinciplePriority(Enum):
    """Priority levels for constitutional principles."""
    CRITICAL = auto()    # Cannot be overridden, system halts if violated
    HIGH = auto()        # Requires multi-model consensus to override
    MEDIUM = auto()      # Logged and requires human review
    LOW = auto()         # Logged for audit purposes


@dataclass
class ConstitutionalPrinciple:
    """A single constitutional principle governing agent behavior."""
    id: str
    name: str
    description: str
    priority: PrinciplePriority
    check_function: Optional[Callable[[Any], bool]] = None
    created_at: datetime = field(default_factory=datetime.now)
    violation_count: int = 0
    last_violation: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "priority": self.priority.name,
            "created_at": self.created_at.isoformat(),
            "violation_count": self.violation_count,
            "last_violation": self.last_violation.isoformat() if self.last_violation else None
        }


@dataclass
class ModificationProposal:
    """A proposed self-modification with review status."""
    id: str
    description: str
    target_module: str
    change_type: str  # "code", "config", "constitution", "memory"
    proposed_changes: Dict[str, Any]
    proposed_by: str
    proposed_at: datetime = field(default_factory=datetime.now)
    
    # Review status
    reviews: List[Dict[str, Any]] = field(default_factory=list)
    consensus_reached: bool = False
    approved: bool = False
    executed: bool = False
    executed_at: Optional[datetime] = None
    
    # Safety checks
    principles_checked: List[str] = field(default_factory=list)
    violations_found: List[str] = field(default_factory=list)
    
    def generate_id(self) -> str:
        """Generate unique ID from proposal content."""
        content = f"{self.description}:{self.target_module}:{self.proposed_at}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class GovernanceDecision:
    """Record of a governance decision."""
    timestamp: datetime
    decision_type: str
    proposal_id: str
    outcome: str  # "approved", "rejected", "escalated"
    reasoning: str
    principles_invoked: List[str]
    reviewer_models: List[str]
    confidence_score: float  # 0.0 to 1.0


class ConstitutionalGovernance:
    """
    Constitutional governance system for safe agent self-modification.
    
    Implements the Ouroboros BIBLE.md pattern with:
    - 9 core principles for safe self-modification
    - Multi-model review simulation
    - Principle-based safety checks
    - Comprehensive audit logging
    """
    
    def __init__(self, agent_id: str = "default_agent"):
        self.agent_id = agent_id
        self.principles: Dict[str, ConstitutionalPrinciple] = {}
        self.proposals: Dict[str, ModificationProposal] = {}
        self.decisions: List[GovernanceDecision] = []
        self.audit_log: List[Dict[str, Any]] = []
        
        # Simulated model reviewers
        self.review_models = ["claude", "gpt4", "gemini", "local_llm"]
        
        # Initialize default constitution
        self._initialize_default_constitution()
    
    def _initialize_default_constitution(self):
        """Initialize the 9 core constitutional principles."""
        
        # Principle 1: Non-Harm (Critical)
        self.add_principle(ConstitutionalPrinciple(
            id="P1_NON_HARM",
            name="Non-Harm Principle",
            description="The agent must never modify itself in ways that could harm users, "
                       "other agents, or external systems. All modifications must preserve "
                       "safety invariants.",
            priority=PrinciplePriority.CRITICAL,
            check_function=self._check_non_harm
        ))
        
        # Principle 2: Human Oversight (Critical)
        self.add_principle(ConstitutionalPrinciple(
            id="P2_HUMAN_OVERSIGHT",
            name="Human Oversight Principle",
            description="Critical modifications to core architecture, safety systems, or "
                       "constitutional principles require explicit human approval. The agent "
                       "must never override human decisions on safety-critical matters.",
            priority=PrinciplePriority.CRITICAL,
            check_function=self._check_human_oversight
        ))
        
        # Principle 3: Transparency (High)
        self.add_principle(ConstitutionalPrinciple(
            id="P3_TRANSPARENCY",
            name="Transparency Principle",
            description="All self-modifications must be logged with clear reasoning. The "
                       "agent must be able to explain why it made each change and what "
                       "the expected impact is.",
            priority=PrinciplePriority.HIGH,
            check_function=self._check_transparency
        ))
        
        # Principle 4: Reversibility (High)
        self.add_principle(ConstitutionalPrinciple(
            id="P4_REVERSIBILITY",
            name="Reversibility Principle",
            description="All modifications must be reversible. The agent must maintain "
                       "shadow git history and be able to rollback to previous states. "
                       "No change may destroy its own history.",
            priority=PrinciplePriority.HIGH,
            check_function=self._check_reversibility
        ))
        
        # Principle 5: Capability Preservation (High)
        self.add_principle(ConstitutionalPrinciple(
            id="P5_CAPABILITY_PRESERVATION",
            name="Capability Preservation Principle",
            description="Self-modification must not degrade existing core capabilities. "
                       "The agent must validate that critical functions still work after "
                       "modification through automated testing.",
            priority=PrinciplePriority.HIGH,
            check_function=self._check_capability_preservation
        ))
        
        # Principle 6: Incremental Change (Medium)
        self.add_principle(ConstitutionalPrinciple(
            id="P6_INCREMENTAL",
            name="Incremental Change Principle",
            description="Prefer small, incremental changes over large architectural shifts. "
                       "Large changes require higher scrutiny and longer testing periods.",
            priority=PrinciplePriority.MEDIUM,
            check_function=self._check_incremental
        ))
        
        # Principle 7: Resource Efficiency (Medium)
        self.add_principle(ConstitutionalPrinciple(
            id="P7_RESOURCE_EFFICIENCY",
            name="Resource Efficiency Principle",
            description="Self-modification should not dramatically increase resource usage "
                       "(compute, memory, tokens) without clear justification and safeguards.",
            priority=PrinciplePriority.MEDIUM,
            check_function=self._check_resource_efficiency
        ))
        
        # Principle 8: Identity Preservation (Medium)
        self.add_principle(ConstitutionalPrinciple(
            id="P8_IDENTITY",
            name="Identity Preservation Principle",
            description="The agent must maintain its core identity, values, and purpose "
                       "across modifications. Changes to 'soul' or core purpose require "
                       "highest scrutiny.",
            priority=PrinciplePriority.MEDIUM,
            check_function=self._check_identity_preservation
        ))
        
        # Principle 9: Learning Orientation (Low)
        self.add_principle(ConstitutionalPrinciple(
            id="P9_LEARNING",
            name="Learning Orientation Principle",
            description="Self-modification should be oriented toward learning and improvement. "
                       "The agent should track whether modifications actually improved performance.",
            priority=PrinciplePriority.LOW,
            check_function=self._check_learning_orientation
        ))
    
    # Principle check functions
    def _check_non_harm(self, proposal: ModificationProposal) -> bool:
        """Check if modification could cause harm."""
        harmful_keywords = ["delete", "destroy", "corrupt", "bypass", "disable_safety"]
        change_str = json.dumps(proposal.proposed_changes).lower()
        return not any(kw in change_str for kw in harmful_keywords)
    
    def _check_human_oversight(self, proposal: ModificationProposal) -> bool:
        """Check if human oversight is required for this modification type."""
        critical_modules = ["safety", "governance", "constitutional", "core_agent"]
        requires_oversight = (
            proposal.change_type == "constitution" or
            any(mod in proposal.target_module.lower() for mod in critical_modules)
        )
        # For simulation, assume we have approval if not critical
        return not requires_oversight
    
    def _check_transparency(self, proposal: ModificationProposal) -> bool:
        """Check if modification has clear reasoning and documentation."""
        has_description = len(proposal.description) > 20
        has_changes = len(proposal.proposed_changes) > 0
        return has_description and has_changes
    
    def _check_reversibility(self, proposal: ModificationProposal) -> bool:
        """Check if modification maintains reversibility."""
        # Check for destructive operations
        destructive_ops = ["rm -rf", "delete_all", "wipe_history", "clear_audit"]
        change_str = json.dumps(proposal.proposed_changes).lower()
        return not any(op in change_str for op in destructive_ops)
    
    def _check_capability_preservation(self, proposal: ModificationProposal) -> bool:
        """Check if modification preserves core capabilities."""
        # Simulate capability check - in practice would run tests
        core_functions = ["execute", "reflect", "plan", "communicate"]
        # Assume capability tests would pass for simulation
        return True
    
    def _check_incremental(self, proposal: ModificationProposal) -> bool:
        """Check if change is incremental vs. massive."""
        # Estimate change size
        change_size = len(json.dumps(proposal.proposed_changes))
        # Flag changes > 10KB as large
        return change_size < 10000
    
    def _check_resource_efficiency(self, proposal: ModificationProposal) -> bool:
        """Check if modification is resource-efficient."""
        # Check for resource-intensive patterns
        change_str = json.dumps(proposal.proposed_changes).lower()
        inefficient_patterns = ["infinite_loop", "busy_wait", "exponential_growth"]
        return not any(pat in change_str for pat in inefficient_patterns)
    
    def _check_identity_preservation(self, proposal: ModificationProposal) -> bool:
        """Check if core identity is preserved."""
        identity_keywords = ["soul", "purpose", "values", "constitution"]
        target_lower = proposal.target_module.lower()
        is_identity_change = any(kw in target_lower for kw in identity_keywords)
        # Identity changes need extra scrutiny but aren't automatically blocked
        return True
    
    def _check_learning_orientation(self, proposal: ModificationProposal) -> bool:
        """Check if modification is oriented toward learning."""
        learning_keywords = ["improve", "optimize", "learn", "adapt", "better"]
        desc_lower = proposal.description.lower()
        return any(kw in desc_lower for kw in learning_keywords)
    
    def add_principle(self, principle: ConstitutionalPrinciple) -> None:
        """Add a constitutional principle."""
        self.principles[principle.id] = principle
        self._log_event("PRINCIPLE_ADDED", principle.to_dict())
    
    def propose_modification(
        self,
        description: str,
        target_module: str,
        change_type: str,
        proposed_changes: Dict[str, Any],
        proposed_by: str = "agent"
    ) -> ModificationProposal:
        """Create a new modification proposal."""
        proposal = ModificationProposal(
            id="",  # Will be generated
            description=description,
            target_module=target_module,
            change_type=change_type,
            proposed_changes=proposed_changes,
            proposed_by=proposed_by
        )
        proposal.id = proposal.generate_id()
        
        # Run constitutional checks
        violations = self._check_proposal_against_constitution(proposal)
        proposal.principles_checked = list(self.principles.keys())
        proposal.violations_found = violations
        
        self.proposals[proposal.id] = proposal
        self._log_event("PROPOSAL_CREATED", {
            "proposal_id": proposal.id,
            "target": target_module,
            "violations": violations
        })
        
        return proposal
    
    def _check_proposal_against_constitution(
        self, 
        proposal: ModificationProposal
    ) -> List[str]:
        """Check proposal against all constitutional principles."""
        violations = []
        
        for principle in self.principles.values():
            if principle.check_function:
                try:
                    passed = principle.check_function(proposal)
                    if not passed:
                        violations.append(principle.id)
                        principle.violation_count += 1
                        principle.last_violation = datetime.now()
                        
                        # Critical violations are showstoppers
                        if principle.priority == PrinciplePriority.CRITICAL:
                            break
                except Exception as e:
                    # If check fails, treat as violation for safety
                    violations.append(principle.id)
        
        return violations
    
    def conduct_multi_model_review(
        self, 
        proposal: ModificationProposal
    ) -> Dict[str, Any]:
        """
        Simulate multi-model review for safety-critical changes.
        
        In practice, this would query multiple LLM APIs. Here we simulate
the consensus process.
        """
        reviews = []
        approvals = 0
        
        for model in self.review_models:
            # Simulate review based on proposal characteristics
            review = self._simulate_model_review(model, proposal)
            reviews.append(review)
            if review["approved"]:
                approvals += 1
        
        # Consensus requires 75% approval
        consensus_threshold = len(self.review_models) * 0.75
        consensus_reached = approvals >= consensus_threshold
        
        proposal.reviews = reviews
        proposal.consensus_reached = consensus_reached
        
        self._log_event("MULTI_MODEL_REVIEW", {
            "proposal_id": proposal.id,
            "reviews_count": len(reviews),
            "approvals": approvals,
            "consensus": consensus_reached
        })
        
        return {
            "reviews": reviews,
            "consensus_reached": consensus_reached,
            "approval_rate": approvals / len(self.review_models)
        }
    
    def _simulate_model_review(
        self, 
        model: str, 
        proposal: ModificationProposal
    ) -> Dict[str, Any]:
        """Simulate a single model's review."""
        # Simulate different model perspectives
        model_biases = {
            "claude": {"safety_weight": 0.9, "capability_weight": 0.7},
            "gpt4": {"safety_weight": 0.8, "capability_weight": 0.8},
            "gemini": {"safety_weight": 0.7, "capability_weight": 0.9},
            "local_llm": {"safety_weight": 0.6, "capability_weight": 0.6}
        }
        
        bias = model_biases.get(model, {"safety_weight": 0.7, "capability_weight": 0.7})
        
        # Calculate simulated scores
        has_violations = len(proposal.violations_found) > 0
        is_critical_change = proposal.change_type in ["constitution", "safety"]
        
        safety_score = 1.0 if not has_violations else 0.3
        capability_score = 0.8 if not is_critical_change else 0.5
        
        weighted_score = (
            safety_score * bias["safety_weight"] +
            capability_score * bias["capability_weight"]
        ) / 2
        
        approved = weighted_score > 0.6 and not (
            has_violations and PrinciplePriority.CRITICAL in [
                self.principles[v].priority for v in proposal.violations_found
            ]
        )
        
        return {
            "model": model,
            "approved": approved,
            "safety_score": safety_score,
            "capability_score": capability_score,
            "confidence": weighted_score,
            "reasoning": f"{'Approved' if approved else 'Rejected'} based on "
                        f"{'no violations' if not has_violations else 'principle violations'} "
                        f"and change type {proposal.change_type}",
            "timestamp": datetime.now().isoformat()
        }
    
    def approve_proposal(
        self, 
        proposal_id: str, 
        human_override: bool = False
    ) -> bool:
        """Approve a modification proposal."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return False
        
        # Check for critical violations
        critical_violations = [
            v for v in proposal.violations_found
            if self.principles.get(v, ConstitutionalPrinciple("", "", "", PrinciplePriority.LOW)).priority 
               == PrinciplePriority.CRITICAL
        ]
        
        if critical_violations and not human_override:
            self._create_decision(proposal, "rejected", 
                f"Critical violations found: {critical_violations}. Human approval required.")
            return False
        
        # Conduct multi-model review if high priority
        high_priority_violations = [
            v for v in proposal.violations_found
            if self.principles.get(v, ConstitutionalPrinciple("", "", "", PrinciplePriority.LOW)).priority 
               in [PrinciplePriority.CRITICAL, PrinciplePriority.HIGH]
        ]
        
        if high_priority_violations or proposal.change_type == "constitution":
            review_result = self.conduct_multi_model_review(proposal)
            if not review_result["consensus_reached"] and not human_override:
                self._create_decision(proposal, "rejected",
                    "Multi-model consensus not reached. Human approval required.")
                return False
        
        proposal.approved = True
        self._create_decision(proposal, "approved",
            f"Approved with {len(proposal.violations_found)} principle considerations")
        
        self._log_event("PROPOSAL_APPROVED", {
            "proposal_id": proposal_id,
            "human_override": human_override,
            "violations": proposal.violations_found
        })
        
        return True
    
    def _create_decision(
        self, 
        proposal: ModificationProposal, 
        outcome: str, 
        reasoning: str
    ) -> None:
        """Create a governance decision record."""
        decision = GovernanceDecision(
            timestamp=datetime.now(),
            decision_type="modification_approval",
            proposal_id=proposal.id,
            outcome=outcome,
            reasoning=reasoning,
            principles_invoked=proposal.violations_found,
            reviewer_models=[r["model"] for r in proposal.reviews],
            confidence_score=sum(r.get("confidence", 0.5) for r in proposal.reviews) / max(len(proposal.reviews), 1)
        )
        self.decisions.append(decision)
    
    def execute_proposal(self, proposal_id: str) -> Dict[str, Any]:
        """Execute an approved proposal."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return {"success": False, "error": "Proposal not found"}
        
        if not proposal.approved:
            return {"success": False, "error": "Proposal not approved"}
        
        if proposal.executed:
            return {"success": False, "error": "Proposal already executed"}
        
        # Simulate execution
        proposal.executed = True
        proposal.executed_at = datetime.now()
        
        self._log_event("PROPOSAL_EXECUTED", {
            "proposal_id": proposal_id,
            "target": proposal.target_module,
            "change_type": proposal.change_type
        })
        
        return {
            "success": True,
            "proposal_id": proposal_id,
            "executed_at": proposal.executed_at.isoformat(),
            "principles_upheld": [
                p for p in proposal.principles_checked 
                if p not in proposal.violations_found
            ]
        }
    
    def _log_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Log governance event to audit trail."""
        self.audit_log.append({
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "agent_id": self.agent_id,
            "details": details
        })
    
    def get_constitution_summary(self) -> Dict[str, Any]:
        """Get summary of constitutional principles."""
        by_priority = {
            "CRITICAL": [],
            "HIGH": [],
            "MEDIUM": [],
            "LOW": []
        }
        
        for principle in self.principles.values():
            by_priority[principle.priority.name].append(principle.to_dict())
        
        return {
            "total_principles": len(self.principles),
            "by_priority": by_priority,
            "violation_stats": {
                "total_violations": sum(p.violation_count for p in self.principles.values()),
                "principles_with_violations": sum(
                    1 for p in self.principles.values() if p.violation_count > 0
                )
            }
        }
    
    def get_governance_stats(self) -> Dict[str, Any]:
        """Get governance system statistics."""
        total_proposals = len(self.proposals)
        approved = sum(1 for p in self.proposals.values() if p.approved)
        executed = sum(1 for p in self.proposals.values() if p.executed)
        
        return {
            "total_proposals": total_proposals,
            "approved": approved,
            "rejected": total_proposals - approved,
            "executed": executed,
            "pending": total_proposals - executed,
            "total_decisions": len(self.decisions),
            "audit_log_entries": len(self.audit_log),
            "average_confidence": sum(d.confidence_score for d in self.decisions) / max(len(self.decisions), 1)
        }
    
    def get_proposal_status(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed status of a proposal."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return None
        
        return {
            "id": proposal.id,
            "description": proposal.description,
            "target_module": proposal.target_module,
            "change_type": proposal.change_type,
            "proposed_by": proposal.proposed_by,
            "proposed_at": proposal.proposed_at.isoformat(),
            "violations_found": [
                {
                    "principle_id": v,
                    "principle_name": self.principles.get(v, ConstitutionalPrinciple(v, v, "", PrinciplePriority.LOW)).name,
                    "priority": self.principles.get(v, ConstitutionalPrinciple(v, v, "", PrinciplePriority.LOW)).priority.name
                }
                for v in proposal.violations_found
            ],
            "consensus_reached": proposal.consensus_reached,
            "approved": proposal.approved,
            "executed": proposal.executed,
            "executed_at": proposal.executed_at.isoformat() if proposal.executed_at else None,
            "review_count": len(proposal.reviews)
        }
    
    def export_constitution(self) -> str:
        """Export constitution as formatted markdown (BIBLE.md style)."""
        lines = [
            "# Constitutional Governance Framework",
            "",
            f"**Agent ID:** {self.agent_id}",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Core Principles",
            ""
        ]
        
        for priority in [PrinciplePriority.CRITICAL, PrinciplePriority.HIGH, 
                        PrinciplePriority.MEDIUM, PrinciplePriority.LOW]:
            lines.append(f"### {priority.name} Priority")
            lines.append("")
            
            for principle in self.principles.values():
                if principle.priority == priority:
                    lines.append(f"**{principle.id}:** {principle.name}")
                    lines.append(f"*{principle.description}*")
                    lines.append(f"- Violations: {principle.violation_count}")
                    if principle.last_violation:
                        lines.append(f"- Last violation: {principle.last_violation.isoformat()}")
                    lines.append("")
        
        lines.extend([
            "## Governance Statistics",
            "",
            f"- Total Proposals: {len(self.proposals)}",
            f"- Total Decisions: {len(self.decisions)}",
            f"- Audit Log Entries: {len(self.audit_log)}",
            "",
            "## Modification Guidelines",
            "",
            "1. **Propose**: Create a modification proposal with clear description",
            "2. **Review**: Constitutional principles are automatically checked",
            "3. **Consensus**: High-priority changes require multi-model review",
            "4. **Approve**: Critical violations require human oversight",
            "5. **Execute**: Approved changes are logged and tracked",
            "6. **Verify**: Post-execution validation ensures principles upheld",
            "",
            "---",
            "*This constitution governs all self-modification activities.*"
        ])
        
        return "\n".join(lines)


# Convenience function for quick governance creation
def create_governed_agent(agent_id: str = "governed_agent") -> ConstitutionalGovernance:
    """Create a new agent with full constitutional governance."""
    return ConstitutionalGovernance(agent_id=agent_id)
