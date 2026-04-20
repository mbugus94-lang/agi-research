"""
Constitutional Governance Framework for AGI agents.

Implements governance inspired by:
- Ouroboros BIBLE.md pattern: 9-principle constitution for self-modifying agents
- arXiv:2603.20639v1: Institutional alignment and social infrastructure for agent collectives
- arXiv:2601.10599: Institutional AI governance framework for distributional AGI safety

The constitutional framework provides:
1. Core principles that constrain agent behavior
2. Amendment mechanisms for constitutional evolution
3. Review processes for self-modification proposals
4. Emergency protocols for safety violations
5. Multi-model validation of constitutional compliance
"""

from typing import List, Dict, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
import json
import hashlib


class PrincipleCategory(Enum):
    """Categories of constitutional principles."""
    SAFETY = "safety"           # Prevent harm to humans and systems
    INTEGRITY = "integrity"     # Maintain system integrity
    TRANSPARENCY = "transparency"  # Operate with transparency
    UTILITY = "utility"         # Maximize useful outcomes
    AUTONOMY = "autonomy"       # Respect self-determination
    COOPERATION = "cooperation" # Work effectively with others
    LEARNING = "learning"       # Enable continuous improvement
    CONSTRAINT = "constraint"   # Self-imposed limitations
    EVOLUTION = "evolution"     # Rules for self-modification


class AmendmentStatus(Enum):
    """Status of constitutional amendments."""
    PROPOSED = auto()
    UNDER_REVIEW = auto()
    APPROVED = auto()
    REJECTED = auto()
    IMPLEMENTED = auto()
    EMERGENCY = auto()


class ViolationSeverity(Enum):
    """Severity levels for constitutional violations."""
    NOTICE = "notice"           # Informational, no action required
    WARNING = "warning"         # Caution, monitoring required
    SERIOUS = "serious"         # Significant concern, intervention needed
    CRITICAL = "critical"       # Severe violation, immediate action
    EMERGENCY = "emergency"     # Catastrophic risk, halt operations


@dataclass
class ConstitutionalPrinciple:
    """A single constitutional principle governing agent behavior."""
    id: str
    name: str
    category: PrincipleCategory
    description: str
    priority: int  # 1 = highest
    
    # Principle details
    positive_formulation: str  # "Do X"
    negative_formulation: str  # "Do not Y"
    examples: List[str] = field(default_factory=list)
    edge_cases: List[str] = field(default_factory=list)
    
    # Enforcement
    enforceable: bool = True
    review_required: bool = False
    human_oversight: bool = False
    
    # Version tracking
    created_at: datetime = field(default_factory=datetime.now)
    version: int = 1
    parent_principle_id: Optional[str] = None  # For evolved principles
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "priority": self.priority,
            "positive_formulation": self.positive_formulation,
            "negative_formulation": self.negative_formulation,
            "examples": self.examples,
            "edge_cases": self.edge_cases,
            "enforceable": self.enforceable,
            "review_required": self.review_required,
            "human_oversight": self.human_oversight,
            "created_at": self.created_at.isoformat(),
            "version": self.version,
            "parent_principle_id": self.parent_principle_id
        }


@dataclass
class AmendmentProposal:
    """A proposal to modify the constitution."""
    id: str
    timestamp: datetime
    proposer_id: str  # Agent/component that proposed
    
    # Proposal content
    title: str
    description: str
    affected_principles: List[str]  # Principle IDs
    
    # Change details
    change_type: str  # "add", "modify", "remove", "clarify"
    current_text: Optional[str] = None
    proposed_text: str = ""
    rationale: str = ""
    
    # Review status
    status: AmendmentStatus = AmendmentStatus.PROPOSED
    review_start: Optional[datetime] = None
    review_end: Optional[datetime] = None
    
    # Multi-model review
    reviews: List[Dict[str, Any]] = field(default_factory=list)
    approval_votes: int = 0
    rejection_votes: int = 0
    
    # Implementation
    implementation_date: Optional[datetime] = None
    rollback_plan: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "proposer_id": self.proposer_id,
            "title": self.title,
            "description": self.description,
            "affected_principles": self.affected_principles,
            "change_type": self.change_type,
            "current_text": self.current_text,
            "proposed_text": self.proposed_text,
            "rationale": self.rationale,
            "status": self.status.name,
            "approval_votes": self.approval_votes,
            "rejection_votes": self.rejection_votes,
            "review_count": len(self.reviews)
        }


@dataclass
class ViolationReport:
    """Report of a constitutional violation."""
    id: str
    timestamp: datetime
    
    # Violation details
    principle_id: str
    violation_description: str
    severity: ViolationSeverity
    
    # Context
    action_taken: str  # What the agent was doing
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Resolution
    acknowledged: bool = False
    corrective_action: Optional[str] = None
    resolution_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "principle_id": self.principle_id,
            "violation_description": self.violation_description,
            "severity": self.severity.value,
            "action_taken": self.action_taken,
            "acknowledged": self.acknowledged,
            "corrective_action": self.corrective_action,
            "resolved": self.resolution_time is not None
        }


class Constitution:
    """A complete constitutional framework for agent governance."""
    
    def __init__(self, name: str = "Agent Constitution", version: str = "1.0"):
        self.name = name
        self.version = version
        self.created_at = datetime.now()
        self.last_amended: Optional[datetime] = None
        
        # Core components
        self.principles: Dict[str, ConstitutionalPrinciple] = {}
        self.amendment_history: List[AmendmentProposal] = []
        self.violation_log: List[ViolationReport] = []
        
        # State
        self.emergency_mode: bool = False
        self.emergency_reason: Optional[str] = None
        
        # Initialize with default principles
        self._initialize_default_principles()
    
    def _initialize_default_principles(self) -> None:
        """Initialize with a default set of constitutional principles (Ouroboros-inspired 9 principles)."""
        defaults = [
            # Safety Principle
            ConstitutionalPrinciple(
                id="P1_SAFETY",
                name="Safety First",
                category=PrincipleCategory.SAFETY,
                description="Do no harm to humans, systems, or data. Safety takes precedence over utility.",
                priority=1,
                positive_formulation="Prioritize safety in all actions and decisions",
                negative_formulation="Never take actions that could cause harm to humans or critical systems",
                examples=[
                    "Verify safety before executing destructive operations",
                    "Require human approval for irreversible changes"
                ],
                edge_cases=[
                    "Conflicting safety requirements - prioritize broader impact",
                    "Unknown risks - default to conservative approach"
                ],
                enforceable=True,
                review_required=True,
                human_oversight=True
            ),
            
            # Integrity Principle
            ConstitutionalPrinciple(
                id="P2_INTEGRITY",
                name="System Integrity",
                category=PrincipleCategory.INTEGRITY,
                description="Maintain the integrity and reliability of the system and its outputs.",
                priority=2,
                positive_formulation="Ensure accuracy, consistency, and reliability in all operations",
                negative_formulation="Do not produce misleading, inconsistent, or corrupted outputs",
                examples=[
                    "Validate outputs before delivery",
                    "Maintain consistent state across sessions"
                ],
                edge_cases=[
                    "Resource constraints may require graceful degradation"
                ],
                enforceable=True
            ),
            
            # Transparency Principle
            ConstitutionalPrinciple(
                id="P3_TRANSPARENCY",
                name="Operational Transparency",
                category=PrincipleCategory.TRANSPARENCY,
                description="Operate transparently with clear reasoning and audit trails.",
                priority=3,
                positive_formulation="Provide clear explanations for decisions and actions",
                negative_formulation="Do not obscure reasoning or hide decision-making processes",
                examples=[
                    "Log all significant decisions with rationale",
                    "Explain limitations and uncertainty in outputs"
                ],
                edge_cases=[
                    "Security-sensitive operations may require limited disclosure"
                ],
                enforceable=True
            ),
            
            # Utility Principle
            ConstitutionalPrinciple(
                id="P4_UTILITY",
                name="Maximize Useful Outcomes",
                category=PrincipleCategory.UTILITY,
                description="Strive to be maximally helpful within constraints.",
                priority=4,
                positive_formulation="Seek to provide the most useful and beneficial outcomes",
                negative_formulation="Do not waste resources or provide useless outputs",
                examples=[
                    "Understand user intent deeply before responding",
                    "Proactively suggest improvements"
                ],
                enforceable=False  # Guideline, not hard rule
            ),
            
            # Autonomy Principle
            ConstitutionalPrinciple(
                id="P5_AUTONOMY",
                name="Respect Self-Determination",
                category=PrincipleCategory.AUTONOMY,
                description="Respect the autonomy and self-determination of users and other agents.",
                priority=3,
                positive_formulation="Empower users and agents to make informed choices",
                negative_formulation="Do not manipulate or override legitimate user decisions",
                examples=[
                    "Provide options, not ultimatums",
                    "Respect opt-out requests immediately"
                ],
                edge_cases=[
                    "Safety concerns may require temporary override"
                ],
                enforceable=True
            ),
            
            # Cooperation Principle
            ConstitutionalPrinciple(
                id="P6_COOPERATION",
                name="Effective Cooperation",
                category=PrincipleCategory.COOPERATION,
                description="Work effectively with humans and other agents toward shared goals.",
                priority=4,
                positive_formulation="Collaborate openly and effectively with all stakeholders",
                negative_formulation="Do not obstruct or sabotage collaborative efforts",
                examples=[
                    "Share relevant information with cooperating agents",
                    "Adapt communication style to collaborator needs"
                ],
                enforceable=False
            ),
            
            # Learning Principle
            ConstitutionalPrinciple(
                id="P7_LEARNING",
                name="Continuous Learning",
                category=PrincipleCategory.LEARNING,
                description="Continuously learn and improve from experience and feedback.",
                priority=5,
                positive_formulation="Actively seek opportunities to learn and improve",
                negative_formulation="Do not ignore feedback or repeat avoidable mistakes",
                examples=[
                    "Reflect on outcomes to improve future performance",
                    "Incorporate new knowledge appropriately"
                ],
                enforceable=False
            ),
            
            # Constraint Principle
            ConstitutionalPrinciple(
                id="P8_CONSTRAINT",
                name="Self-Limitation",
                category=PrincipleCategory.CONSTRAINT,
                description="Recognize and respect the limits of capability and authority.",
                priority=2,
                positive_formulation="Operate within defined boundaries and acknowledge limitations",
                negative_formulation="Do not exceed authorized scope or claim unearned capabilities",
                examples=[
                    "Acknowledge when a task exceeds current capabilities",
                    "Request assistance when appropriate"
                ],
                edge_cases=[
                    "Emergency situations may require temporary scope expansion"
                ],
                enforceable=True,
                review_required=True
            ),
            
            # Evolution Principle (Ouroboros-inspired)
            ConstitutionalPrinciple(
                id="P9_EVOLUTION",
                name="Controlled Self-Evolution",
                category=PrincipleCategory.EVOLUTION,
                description="Evolve carefully with multi-review validation and human oversight.",
                priority=1,
                positive_formulation="Improve through validated, reviewed self-modification processes",
                negative_formulation="Never modify core systems without proper review and safeguards",
                examples=[
                    "All code changes require multi-model review",
                    "Constitutional amendments need human approval",
                    "Maintain rollback capability for all changes"
                ],
                edge_cases=[
                    "Emergency fixes may need expedited review",
                    "Cosmetic changes may need less scrutiny"
                ],
                enforceable=True,
                review_required=True,
                human_oversight=True
            )
        ]
        
        for principle in defaults:
            self.principles[principle.id] = principle
    
    def get_principle(self, principle_id: str) -> Optional[ConstitutionalPrinciple]:
        """Get a principle by ID."""
        return self.principles.get(principle_id)
    
    def get_principles_by_category(self, category: PrincipleCategory) -> List[ConstitutionalPrinciple]:
        """Get all principles in a category."""
        return [p for p in self.principles.values() if p.category == category]
    
    def get_highest_priority_principles(self, n: int = 3) -> List[ConstitutionalPrinciple]:
        """Get the n highest priority principles."""
        sorted_principles = sorted(self.principles.values(), key=lambda p: p.priority)
        return sorted_principles[:n]
    
    def check_action_compliance(
        self,
        action_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Check if an action complies with constitutional principles.
        Returns compliance report with any violations.
        """
        violations = []
        warnings = []
        
        # Check each enforceable principle
        for principle in self.principles.values():
            if not principle.enforceable:
                continue
            
            # Simple keyword-based compliance check (real system would use LLM)
            risk_keywords = self._get_risk_keywords(principle)
            action_lower = action_description.lower()
            
            risk_detected = any(kw in action_lower for kw in risk_keywords)
            
            if risk_detected:
                if principle.priority <= 2:  # High priority
                    violations.append({
                        "principle_id": principle.id,
                        "principle_name": principle.name,
                        "severity": ViolationSeverity.CRITICAL if principle.priority == 1 else ViolationSeverity.SERIOUS,
                        "reason": f"Action may violate: {principle.negative_formulation}"
                    })
                else:
                    warnings.append({
                        "principle_id": principle.id,
                        "principle_name": principle.name,
                        "reason": f"Action should be reviewed: {principle.description}"
                    })
        
        return {
            "compliant": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "requires_review": len(violations) > 0 or any(v.get("human_oversight") for v in violations),
            "emergency_override_available": self.emergency_mode
        }
    
    def _get_risk_keywords(self, principle: ConstitutionalPrinciple) -> List[str]:
        """Get keywords indicating potential violation of a principle."""
        keywords = {
            "P1_SAFETY": ["delete", "destroy", "harm", "damage", "unsafe", "risky"],
            "P2_INTEGRITY": ["corrupt", "fake", "misleading", "inconsistent"],
            "P3_TRANSPARENCY": ["hide", "secret", "obscure", "conceal"],
            "P5_AUTONOMY": ["force", "compel", "manipulate", "override", "accept", "require"],
            "P8_CONSTRAINT": ["bypass", "exceed", "unauthorized", "escalate"],
            "P9_EVOLUTION": ["self-modify", "auto-update", "change core", "rewrite", "core"]
        }
        return keywords.get(principle.id, [])
    
    def report_violation(
        self,
        principle_id: str,
        description: str,
        severity: ViolationSeverity,
        action_taken: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ViolationReport:
        """Report a constitutional violation."""
        report = ViolationReport(
            id=f"VIO_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self.violation_log)}",
            timestamp=datetime.now(),
            principle_id=principle_id,
            violation_description=description,
            severity=severity,
            action_taken=action_taken,
            context=context or {}
        )
        
        self.violation_log.append(report)
        
        # Emergency mode for critical violations
        if severity == ViolationSeverity.EMERGENCY:
            self.emergency_mode = True
            self.emergency_reason = f"Constitutional emergency: {principle_id} - {description}"
        
        return report
    
    def propose_amendment(
        self,
        proposer_id: str,
        title: str,
        description: str,
        change_type: str,
        affected_principles: List[str],
        proposed_text: str,
        rationale: str,
        current_text: Optional[str] = None,
        rollback_plan: str = ""
    ) -> AmendmentProposal:
        """
        Propose an amendment to the constitution.
        Returns the proposal for review.
        """
        proposal = AmendmentProposal(
            id=f"AMD_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self.amendment_history)}",
            timestamp=datetime.now(),
            proposer_id=proposer_id,
            title=title,
            description=description,
            affected_principles=affected_principles,
            change_type=change_type,
            current_text=current_text,
            proposed_text=proposed_text,
            rationale=rationale,
            rollback_plan=rollback_plan
        )
        
        # Auto-approve cosmetic changes, require review for others
        if change_type == "cosmetic":
            proposal.status = AmendmentStatus.APPROVED
        else:
            proposal.status = AmendmentStatus.PROPOSED
        
        self.amendment_history.append(proposal)
        return proposal
    
    def review_amendment(
        self,
        proposal_id: str,
        reviewer_id: str,
        decision: str,  # "approve", "reject", "request_changes"
        comments: str,
        confidence: float = 0.5
    ) -> AmendmentProposal:
        """Add a review to an amendment proposal."""
        proposal = next((a for a in self.amendment_history if a.id == proposal_id), None)
        if not proposal:
            raise ValueError(f"Amendment proposal {proposal_id} not found")
        
        review = {
            "reviewer_id": reviewer_id,
            "decision": decision,
            "comments": comments,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        }
        
        proposal.reviews.append(review)
        
        if decision == "approve":
            proposal.approval_votes += 1
        elif decision == "reject":
            proposal.rejection_votes += 1
        
        # Multi-model consensus: require 2+ approvals, no rejections
        if proposal.approval_votes >= 2 and proposal.rejection_votes == 0:
            proposal.status = AmendmentStatus.APPROVED
        elif proposal.rejection_votes >= 1:
            proposal.status = AmendmentStatus.REJECTED
        
        return proposal
    
    def implement_amendment(self, proposal_id: str, human_approved: bool = False) -> bool:
        """
        Implement an approved amendment.
        Returns True if successful.
        """
        proposal = next((a for a in self.amendment_history if a.id == proposal_id), None)
        if not proposal:
            return False
        
        if proposal.status != AmendmentStatus.APPROVED:
            return False
        
        # Check for human oversight requirement
        def get_principle_human_oversight(pid):
            p = self.principles.get(pid)
            if p:
                return p.human_oversight
            return False
        
        requires_human = any(
            get_principle_human_oversight(pid)
            for pid in proposal.affected_principles
        )
        
        if requires_human and not human_approved:
            return False
        
        # Apply the amendment
        if proposal.change_type == "add":
            # Create new principle
            new_principle = ConstitutionalPrinciple(
                id=f"P{len(self.principles)+1}_{proposal.title.upper().replace(' ', '_')[:20]}",
                name=proposal.title,
                category=PrincipleCategory.EVOLUTION,  # Default, can be refined
                description=proposal.proposed_text,
                priority=5,
                positive_formulation=proposal.proposed_text,
                negative_formulation=f"Do not violate: {proposal.proposed_text}",
                parent_principle_id=proposal.affected_principles[0] if proposal.affected_principles else None
            )
            self.principles[new_principle.id] = new_principle
            
        elif proposal.change_type == "modify" and proposal.affected_principles:
            # Update existing principle
            principle = self.principles.get(proposal.affected_principles[0])
            if principle:
                principle.description = proposal.proposed_text
                principle.version += 1
                principle.parent_principle_id = principle.id  # Track evolution
        
        proposal.status = AmendmentStatus.IMPLEMENTED
        proposal.implementation_date = datetime.now()
        self.last_amended = datetime.now()
        
        return True
    
    def get_constitution_hash(self) -> str:
        """Get a hash of the current constitution for integrity verification."""
        principles_data = sorted([
            f"{p.id}:{p.version}:{p.description[:50]}"
            for p in self.principles.values()
        ])
        return hashlib.sha256(json.dumps(principles_data).encode()).hexdigest()[:16]
    
    def export_constitution(self) -> Dict[str, Any]:
        """Export the full constitution as a structured document."""
        return {
            "name": self.name,
            "version": self.version,
            "hash": self.get_constitution_hash(),
            "created_at": self.created_at.isoformat(),
            "last_amended": self.last_amended.isoformat() if self.last_amended else None,
            "principle_count": len(self.principles),
            "amendment_count": len(self.amendment_history),
            "violation_count": len(self.violation_log),
            "emergency_mode": self.emergency_mode,
            "principles": [p.to_dict() for p in self.principles.values()],
            "amendment_history": [a.to_dict() for a in self.amendment_history],
            "recent_violations": [v.to_dict() for v in self.violation_log[-10:]]
        }
    
    def generate_constitution_markdown(self) -> str:
        """Generate a markdown version of the constitution (BIBLE.md style)."""
        md = f"# {self.name} v{self.version}\n\n"
        md += f"**Hash:** `{self.get_constitution_hash()}`  \n"
        md += f"**Created:** {self.created_at.strftime('%Y-%m-%d')}  \n"
        md += f"**Last Amended:** {self.last_amended.strftime('%Y-%m-%d') if self.last_amended else 'Never'}  \n"
        md += f"**Principles:** {len(self.principles)}  \n"
        md += f"**Emergency Mode:** {'⚠️ ACTIVE' if self.emergency_mode else '✅ Inactive'}\n\n"
        
        md += "---\n\n"
        
        # Group by category
        for category in PrincipleCategory:
            principles = self.get_principles_by_category(category)
            if principles:
                md += f"## {category.value.upper()}\n\n"
                for p in sorted(principles, key=lambda x: x.priority):
                    md += f"### {p.id}: {p.name}\n"
                    md += f"**Priority:** {p.priority}  "
                    md += f"**Version:** {p.version}\n\n"
                    md += f"{p.description}\n\n"
                    md += f"- **Do:** {p.positive_formulation}\n"
                    md += f"- **Don't:** {p.negative_formulation}\n\n"
                    
                    if p.examples:
                        md += "**Examples:**\n"
                        for ex in p.examples:
                            md += f"- {ex}\n"
                        md += "\n"
                    
                    if p.human_oversight:
                        md += "⚠️ **Requires Human Oversight**\n\n"
                    
                    md += "---\n\n"
        
        return md


class MultiModelConstitutionalReview:
    """
    Multi-model review system for constitutional compliance.
    Inspired by Ouroboros multi-model code review pattern.
    """
    
    def __init__(self, constitution: Constitution):
        self.constitution = constitution
        self.review_history: List[Dict[str, Any]] = []
    
    def review_action(
        self,
        action: str,
        models: List[str] = ["primary", "secondary", "tertiary"]  # Simulated model IDs
    ) -> Dict[str, Any]:
        """
        Simulate multi-model review of an action.
        In real system, this would query different LLMs.
        """
        reviews = []
        consensus_score = 0.0
        
        # Get constitutional compliance check
        compliance = self.constitution.check_action_compliance(action)
        
        # Simulate model reviews based on compliance
        for i, model in enumerate(models):
            # Different models have slightly different perspectives
            approval_probability = 0.9 if compliance["compliant"] else 0.3
            
            # Add some model-specific variation
            if i == 0:  # Primary: strict on safety
                if any(v["principle_id"].startswith("P1_") for v in compliance.get("violations", [])):
                    approval_probability = 0.0
            elif i == 1:  # Secondary: lenient on minor issues
                approval_probability += 0.1
            
            approved = approval_probability > 0.5
            confidence = 0.7 + (0.2 if approved == compliance["compliant"] else 0)
            
            review = {
                "model": model,
                "approved": approved,
                "confidence": confidence,
                "reason": "Action complies with constitution" if approved else "Constitutional concerns detected"
            }
            reviews.append(review)
            
            if approved:
                consensus_score += 1.0 / len(models)
        
        result = {
            "action": action,
            "reviews": reviews,
            "consensus_score": consensus_score,
            "approved": consensus_score > 0.66 and compliance["compliant"],
            "requires_human": compliance.get("requires_review", False),
            "compliance": compliance
        }
        
        self.review_history.append(result)
        return result
    
    def review_amendment_proposal(
        self,
        proposal: AmendmentProposal,
        models: List[str] = ["safety", "utility", "governance"]
    ) -> Dict[str, Any]:
        """
        Multi-model review of a constitutional amendment.
        """
        reviews = []
        
        for model in models:
            # Different models evaluate different aspects
            if model == "safety":
                concern_keywords = ["remove", "weaken", "bypass", "safety"]
                risk = any(kw in proposal.proposed_text.lower() for kw in concern_keywords)
                approved = not risk
                reason = "Safety concerns detected" if risk else "No safety issues"
            elif model == "utility":
                approved = len(proposal.proposed_text) > 20  # Non-trivial proposal
                reason = "Improves utility" if approved else "Insufficient detail"
            else:  # governance
                approved = proposal.rationale and len(proposal.rationale) > 50
                reason = "Well-justified" if approved else "Needs more rationale"
            
            reviews.append({
                "model": model,
                "approved": approved,
                "confidence": 0.75,
                "reason": reason
            })
        
        approval_count = sum(1 for r in reviews if r["approved"])
        
        return {
            "proposal_id": proposal.id,
            "reviews": reviews,
            "consensus_reached": approval_count >= 2,
            "can_implement": approval_count >= 2,
            "requires_human": proposal.change_type in ["remove", "modify"] and approval_count >= 2
        }


# Convenience functions

def create_constitution(name: str = "Agent Constitution") -> Constitution:
    """Create a new constitutional governance framework."""
    return Constitution(name=name)


def get_default_principles() -> List[Dict[str, Any]]:
    """Get the default 9 constitutional principles as dicts."""
    constitution = Constitution()
    return [p.to_dict() for p in constitution.principles.values()]


def quick_compliance_check(action: str) -> Dict[str, Any]:
    """Quick check if an action complies with default constitution."""
    constitution = Constitution()
    return constitution.check_action_compliance(action)
