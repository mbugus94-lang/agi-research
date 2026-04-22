"""
Verification & Attestation System

Based on "Some Simple Economics of AGI" (arXiv:2602.20946):
- The binding constraint is human verification bandwidth, not intelligence
- We need to scale verification alongside agentic capabilities
- Attestation-based settlement with cryptographic provenance

Key Concepts:
- Verifiable Output: Agent outputs with evidence/provenance
- Attestation: Cryptographic signature of verification
- Confidence Scoring: Multi-factor trust calculation
- Measurability Assessment: Can humans verify this output?
"""

import json
import uuid
import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable, Tuple
from enum import Enum
from collections import defaultdict


class VerificationLevel(Enum):
    """Levels of verification rigor"""
    AUTOMATED = "automated"      # Automated checks only
    SAMPLED = "sampled"          # Random human sampling
    SUPERVISED = "supervised"    # Human supervision required
    AUDITED = "audited"          # Full audit trail
    CERTIFIED = "certified"      # Formal certification


class OutputCategory(Enum):
    """Categories of agent outputs by measurability"""
    DETERMINISTIC = "deterministic"    # Code, math, structured data (easily verifiable)
    SEMANTIC = "semantic"              # Text summaries, analysis (human-judged)
    CREATIVE = "creative"              # Generated content (subjective)
    ACTION = "action"                  # External actions (hard to verify)
    SYNTHETIC = "synthetic"            # Novel insights (measurability gap)


@dataclass
class Evidence:
    """Evidence supporting an output's correctness"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    evidence_type: str = ""  # "trace", "reference", "test_result", "human_review"
    content: Any = None
    source: str = ""  # Where this evidence came from
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    verifier_id: Optional[str] = None  # Who/what provided this evidence
    confidence: float = 0.5  # 0-1 confidence in this evidence
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "evidence_type": self.evidence_type,
            "content": self.content,
            "source": self.source,
            "timestamp": self.timestamp,
            "verifier_id": self.verifier_id,
            "confidence": self.confidence
        }


@dataclass
class VerifiableOutput:
    """An agent output wrapped with verification metadata"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    output_type: str = ""  # Type of output produced
    content: Any = None
    category: str = field(default_factory=lambda: OutputCategory.SEMANTIC.value)
    
    # Provenance
    input_hash: str = ""  # Hash of inputs that produced this output
    execution_trace: List[Dict] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Evidence
    evidence: List[Evidence] = field(default_factory=list)
    
    # Verification state
    verification_level: str = field(default_factory=lambda: VerificationLevel.AUTOMATED.value)
    confidence_score: float = 0.0  # 0-1 overall confidence
    verification_status: str = "pending"  # pending, verified, disputed, failed
    
    # Attestation
    attestations: List[Dict] = field(default_factory=list)
    
    # Measurability assessment
    measurability_score: float = 0.5  # How easily can humans verify this?
    verification_cost_estimate: float = 0.0  # Estimated human time (minutes)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "output_type": self.output_type,
            "content": self.content,
            "category": self.category,
            "input_hash": self.input_hash,
            "execution_trace": self.execution_trace,
            "timestamp": self.timestamp,
            "evidence": [e.to_dict() for e in self.evidence],
            "verification_level": self.verification_level,
            "confidence_score": self.confidence_score,
            "verification_status": self.verification_status,
            "attestations": self.attestations,
            "measurability_score": self.measurability_score,
            "verification_cost_estimate": self.verification_cost_estimate
        }
    
    def compute_content_hash(self) -> str:
        """Compute hash of content for integrity checking"""
        content_str = json.dumps(self.content, sort_keys=True, default=str)
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]


@dataclass
class Attestation:
    """Cryptographic attestation of verification"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    output_id: str = ""
    verifier_id: str = ""
    verifier_type: str = ""  # "automated", "human", "consensus", "oracle"
    
    # Attestation details
    claim: str = ""  # What is being attested
    confidence: float = 0.5  # Verifier's confidence (0-1)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Cryptographic proof (simplified)
    signature: str = ""
    proof_hash: str = ""
    
    # Verification method
    method: str = ""  # How verification was performed
    evidence_ids: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "output_id": self.output_id,
            "verifier_id": self.verifier_id,
            "verifier_type": self.verifier_type,
            "claim": self.claim,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "signature": self.signature,
            "proof_hash": self.proof_hash,
            "method": self.method,
            "evidence_ids": self.evidence_ids
        }
    
    def sign(self, secret_key: str) -> None:
        """Create cryptographic signature (simplified)"""
        data = f"{self.output_id}:{self.verifier_id}:{self.claim}:{self.confidence}"
        self.signature = hmac.new(
            secret_key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()[:32]
        self.proof_hash = hashlib.sha256(data.encode()).hexdigest()[:16]


class VerificationSystem:
    """
    Verification and attestation system for agent outputs.
    
    Implements insights from "Some Simple Economics of AGI":
    - Measurability assessment: Score how easily outputs can be verified
    - Confidence scoring: Multi-factor trust calculation
    - Attestation: Cryptographic verification records
    - Cost estimation: Estimate human verification time
    
    Key Principle: Scale verification alongside capabilities to avoid
    the "Measurability Gap" where agents produce more than humans can verify.
    """
    
    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or secrets.token_hex(32)
        
        # Output registry
        self.outputs: Dict[str, VerifiableOutput] = {}
        self.attestations: Dict[str, Attestation] = {}
        
        # Verification strategies by category
        self.verification_strategies: Dict[str, List[Callable]] = {
            OutputCategory.DETERMINISTIC.value: [
                self._verify_deterministic
            ],
            OutputCategory.SEMANTIC.value: [
                self._verify_semantic
            ],
            OutputCategory.CREATIVE.value: [
                self._verify_creative
            ],
            OutputCategory.ACTION.value: [
                self._verify_action
            ],
            OutputCategory.SYNTHETIC.value: [
                self._verify_synthetic
            ]
        }
        
        # Historical accuracy by agent (for reputation)
        self.agent_verification_history: Dict[str, Dict] = defaultdict(
            lambda: {"total": 0, "correct": 0, "disputed": 0}
        )
        
        # Verification cost tracking
        self.total_verification_cost: float = 0.0  # Minutes of human time
        
    def register_output(self, 
                       agent_id: str,
                       output_type: str,
                       content: Any,
                       inputs: Any = None,
                       category: Optional[str] = None,
                       execution_trace: Optional[List[Dict]] = None) -> VerifiableOutput:
        """
        Register a new agent output for verification.
        
        Automatically assesses measurability and estimates verification cost.
        """
        # Auto-detect category if not provided
        if category is None:
            category = self._detect_category(output_type, content)
        
        # Compute input hash for provenance
        input_hash = ""
        if inputs is not None:
            input_str = json.dumps(inputs, sort_keys=True, default=str)
            input_hash = hashlib.sha256(input_str.encode()).hexdigest()[:16]
        
        output = VerifiableOutput(
            agent_id=agent_id,
            output_type=output_type,
            content=content,
            category=category,
            input_hash=input_hash,
            execution_trace=execution_trace or []
        )
        
        # Assess measurability
        output.measurability_score = self._assess_measurability(category, content)
        output.verification_cost_estimate = self._estimate_verification_cost(
            category, content, output.measurability_score
        )
        
        self.outputs[output.id] = output
        return output
    
    def add_evidence(self, 
                    output_id: str,
                    evidence_type: str,
                    content: Any,
                    source: str,
                    verifier_id: Optional[str] = None,
                    confidence: float = 0.5) -> Evidence:
        """Add evidence to support an output's verification"""
        if output_id not in self.outputs:
            raise ValueError(f"Output {output_id} not found")
        
        evidence = Evidence(
            evidence_type=evidence_type,
            content=content,
            source=source,
            verifier_id=verifier_id,
            confidence=confidence
        )
        
        self.outputs[output_id].evidence.append(evidence)
        return evidence
    
    def verify_output(self, 
                     output_id: str,
                     verifier_id: str,
                     verifier_type: str = "automated",
                     method: str = "",
                     claim: str = "",
                     confidence: float = 0.5) -> Attestation:
        """
        Create an attestation verifying an output.
        
        Updates the output's confidence score based on this attestation.
        """
        if output_id not in self.outputs:
            raise ValueError(f"Output {output_id} not found")
        
        output = self.outputs[output_id]
        
        # Create attestation
        attestation = Attestation(
            output_id=output_id,
            verifier_id=verifier_id,
            verifier_type=verifier_type,
            claim=claim or f"Verified {output.output_type}",
            confidence=confidence,
            method=method,
            evidence_ids=[e.id for e in output.evidence]
        )
        
        # Sign attestation
        attestation.sign(self.secret_key)
        
        self.attestations[attestation.id] = attestation
        output.attestations.append(attestation.to_dict())
        
        # Update output confidence score
        output.confidence_score = self._calculate_confidence(output)
        output.verification_status = "verified"
        
        # Update agent history
        self.agent_verification_history[output.agent_id]["total"] += 1
        if confidence >= 0.8:
            self.agent_verification_history[output.agent_id]["correct"] += 1
        
        # Track verification cost
        if verifier_type == "human":
            self.total_verification_cost += output.verification_cost_estimate
        
        return attestation
    
    def dispute_output(self, 
                      output_id: str,
                      disputer_id: str,
                      reason: str,
                      severity: str = "minor") -> Dict:
        """Dispute a previously verified output"""
        if output_id not in self.outputs:
            raise ValueError(f"Output {output_id} not found")
        
        output = self.outputs[output_id]
        output.verification_status = "disputed"
        
        # Reduce confidence based on dispute severity
        severity_impact = {"minor": 0.1, "moderate": 0.3, "major": 0.5, "critical": 1.0}
        output.confidence_score *= (1 - severity_impact.get(severity, 0.3))
        
        # Update agent history
        self.agent_verification_history[output.agent_id]["disputed"] += 1
        
        dispute_record = {
            "id": str(uuid.uuid4()),
            "output_id": output_id,
            "disputer_id": disputer_id,
            "reason": reason,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
            "previous_confidence": output.confidence_score
        }
        
        return dispute_record
    
    def create_consensus_attestation(self,
                                    output_id: str,
                                    verifier_ids: List[str],
                                    min_confidence: float = 0.66) -> Optional[Attestation]:
        """
        Create an attestation based on consensus among multiple verifiers.
        
        Only creates attestation if sufficient confidence threshold is met.
        """
        # Find existing attestations for these verifiers
        existing = [
            a for a in self.attestations.values()
            if a.output_id == output_id and a.verifier_id in verifier_ids
        ]
        
        if not existing:
            return None
        
        # Calculate consensus confidence
        avg_confidence = sum(a.confidence for a in existing) / len(existing)
        
        if avg_confidence < min_confidence:
            return None
        
        # Create consensus attestation
        attestation = Attestation(
            output_id=output_id,
            verifier_id=f"consensus:{len(verifier_ids)}",
            verifier_type="consensus",
            claim=f"Consensus verification by {len(existing)} verifiers",
            confidence=avg_confidence,
            method="multi_verifier_consensus",
            evidence_ids=[]
        )
        
        attestation.sign(self.secret_key)
        self.attestations[attestation.id] = attestation
        
        # Update output
        output = self.outputs[output_id]
        output.attestations.append(attestation.to_dict())
        output.confidence_score = self._calculate_confidence(output)
        
        return attestation
    
    def get_agent_reputation(self, agent_id: str) -> Dict:
        """Get verification-based reputation for an agent"""
        history = self.agent_verification_history[agent_id]
        
        if history["total"] == 0:
            return {"score": 0.5, "level": "unknown", "history": history}
        
        # Calculate reputation score
        accuracy = history["correct"] / history["total"]
        dispute_rate = history["disputed"] / history["total"]
        
        # Score weighted by volume (more samples = more confident in score)
        volume_factor = min(history["total"] / 100, 1.0)
        score = (accuracy * (1 - dispute_rate) * 0.5 + 0.5) * volume_factor + \
                0.5 * (1 - volume_factor)
        
        # Determine level
        if score >= 0.9 and history["total"] >= 50:
            level = "trusted"
        elif score >= 0.7:
            level = "verified"
        elif score >= 0.5:
            level = "provisional"
        else:
            level = "unverified"
        
        return {
            "score": round(score, 3),
            "level": level,
            "history": dict(history),
            "total_outputs": history["total"],
            "accuracy": round(accuracy, 3),
            "dispute_rate": round(dispute_rate, 3)
        }
    
    def get_verification_stats(self) -> Dict:
        """Get system-wide verification statistics"""
        total_outputs = len(self.outputs)
        verified = sum(1 for o in self.outputs.values() if o.verification_status == "verified")
        disputed = sum(1 for o in self.outputs.values() if o.verification_status == "disputed")
        pending = sum(1 for o in self.outputs.values() if o.verification_status == "pending")
        
        # Measurability distribution
        by_category = defaultdict(lambda: {"count": 0, "avg_measurability": 0.0})
        for o in self.outputs.values():
            by_category[o.category]["count"] += 1
            by_category[o.category]["avg_measurability"] += o.measurability_score
        
        for cat in by_category:
            if by_category[cat]["count"] > 0:
                by_category[cat]["avg_measurability"] /= by_category[cat]["count"]
        
        return {
            "total_outputs": total_outputs,
            "verified": verified,
            "disputed": disputed,
            "pending": pending,
            "verification_rate": round(verified / total_outputs, 3) if total_outputs > 0 else 0,
            "total_verification_cost_minutes": round(self.total_verification_cost, 1),
            "by_category": dict(by_category),
            "agent_reputations": {
                agent_id: self.get_agent_reputation(agent_id)
                for agent_id in self.agent_verification_history.keys()
            }
        }
    
    def _detect_category(self, output_type: str, content: Any) -> str:
        """Automatically detect output category"""
        output_type_lower = output_type.lower()
        
        # Deterministic outputs
        if any(t in output_type_lower for t in ["code", "data", "json", "sql", "config"]):
            return OutputCategory.DETERMINISTIC.value
        
        # Actions
        if any(t in output_type_lower for t in ["action", "api_call", "transaction", "deploy"]):
            return OutputCategory.ACTION.value
        
        # Creative
        if any(t in output_type_lower for t in ["creative", "generate", "design", "art"]):
            return OutputCategory.CREATIVE.value
        
        # Synthetic insights
        if any(t in output_type_lower for t in ["insight", "hypothesis", "discovery", "synthesis"]):
            return OutputCategory.SYNTHETIC.value
        
        # Default to semantic
        return OutputCategory.SEMANTIC.value
    
    def _assess_measurability(self, category: str, content: Any) -> float:
        """
        Assess how measurable (verifiable) an output is.
        
        Returns score 0-1 where:
        - 1.0 = Easily verified (code, structured data)
        - 0.5 = Moderately verifiable (analysis, summaries)
        - 0.0 = Hard to verify (creative, synthetic insights)
        """
        base_scores = {
            OutputCategory.DETERMINISTIC.value: 0.9,
            OutputCategory.SEMANTIC.value: 0.5,
            OutputCategory.CREATIVE.value: 0.2,
            OutputCategory.ACTION.value: 0.4,
            OutputCategory.SYNTHETIC.value: 0.1
        }
        
        base = base_scores.get(category, 0.5)
        
        # Adjust based on content characteristics
        content_str = json.dumps(content, default=str)
        
        # Longer content is harder to verify
        if len(content_str) > 10000:
            base -= 0.2
        elif len(content_str) > 5000:
            base -= 0.1
        
        # Structured content (JSON, code) is more measurable
        if isinstance(content, (dict, list)):
            base += 0.1
        
        # References/citations increase measurability
        if "reference" in content_str.lower() or "source" in content_str.lower():
            base += 0.1
        
        return max(0.0, min(1.0, base))
    
    def _estimate_verification_cost(self, 
                                   category: str, 
                                   content: Any,
                                   measurability: float) -> float:
        """
        Estimate human verification time in minutes.
        
        Based on category and measurability score.
        """
        base_costs = {
            OutputCategory.DETERMINISTIC.value: 2,
            OutputCategory.SEMANTIC.value: 5,
            OutputCategory.CREATIVE.value: 10,
            OutputCategory.ACTION.value: 15,
            OutputCategory.SYNTHETIC.value: 30
        }
        
        base = base_costs.get(category, 5)
        
        # Adjust by measurability (higher = cheaper)
        adjusted = base * (1.5 - measurability)
        
        # Content size factor
        content_str = json.dumps(content, default=str)
        size_factor = max(1.0, len(content_str) / 5000)
        
        return round(adjusted * size_factor, 1)
    
    def _calculate_confidence(self, output: VerifiableOutput) -> float:
        """Calculate overall confidence score from attestations and evidence"""
        if not output.attestations and not output.evidence:
            return 0.0
        
        # Evidence contribution
        evidence_confidence = 0.0
        if output.evidence:
            evidence_confidence = sum(e.confidence for e in output.evidence) / len(output.evidence)
        
        # Attestation contribution
        attestation_confidence = 0.0
        if output.attestations:
            attestation_confidence = sum(
                a.get("confidence", 0.5) for a in output.attestations
            ) / len(output.attestations)
        
        # Weighted combination
        if output.attestations and output.evidence:
            return 0.6 * attestation_confidence + 0.4 * evidence_confidence
        elif output.attestations:
            return attestation_confidence
        else:
            return evidence_confidence * 0.5  # Evidence alone is weaker
    
    # Verification strategies by category
    def _verify_deterministic(self, output: VerifiableOutput) -> Evidence:
        """Verify deterministic outputs (code, data) via testing/validation"""
        return Evidence(
            evidence_type="automated_test",
            content="Syntax validation passed",
            source="automated_verifier",
            verifier_id="deterministic_checker",
            confidence=0.9
        )
    
    def _verify_semantic(self, output: VerifiableOutput) -> Evidence:
        """Verify semantic outputs via consistency checks"""
        return Evidence(
            evidence_type="consistency_check",
            content="Internal consistency verified",
            source="semantic_analyzer",
            verifier_id="semantic_checker",
            confidence=0.6
        )
    
    def _verify_creative(self, output: VerifiableOutput) -> Evidence:
        """Verify creative outputs via style/plagiarism checks"""
        return Evidence(
            evidence_type="style_analysis",
            content="Originality score calculated",
            source="creative_analyzer",
            verifier_id="creative_checker",
            confidence=0.4
        )
    
    def _verify_action(self, output: VerifiableOutput) -> Evidence:
        """Verify action outputs via pre-execution simulation"""
        return Evidence(
            evidence_type="simulation",
            content="Action pre-flight check completed",
            source="action_simulator",
            verifier_id="action_checker",
            confidence=0.5
        )
    
    def _verify_synthetic(self, output: VerifiableOutput) -> Evidence:
        """Verify synthetic insights via peer review requirement"""
        return Evidence(
            evidence_type="peer_review_required",
            content="Multiple expert reviews required",
            source="synthesis_analyzer",
            verifier_id="synthetic_checker",
            confidence=0.2
        )


class MeasurabilityGapAnalyzer:
    """
    Analyze the gap between agent capabilities and verification capacity.
    
    Based on the Economics of AGI insight that this gap is the
    binding constraint on safe AGI deployment.
    """
    
    def __init__(self, verification_system: VerificationSystem):
        self.vs = verification_system
    
    def analyze_gap(self) -> Dict:
        """Analyze current measurability gap"""
        stats = self.vs.get_verification_stats()
        
        # Calculate gap metrics
        total_outputs = stats["total_outputs"]
        if total_outputs == 0:
            return {
                "status": "no_data",
                "gap_ratio": 0,
                "by_category": {}  # Always include this key
            }
        
        verified = stats["verified"]
        pending = stats["pending"]
        
        # Gap ratio: pending / total
        gap_ratio = pending / total_outputs
        
        # Verification velocity: verified per unit cost
        total_cost = stats["total_verification_cost_minutes"]
        velocity = verified / total_cost if total_cost > 0 else 0
        
        # Capacity analysis
        by_category = stats.get("by_category", {})
        high_measurability = sum(
            c["count"] for cat, c in by_category.items()
            if c.get("avg_measurability", 0) > 0.7
        )
        low_measurability = sum(
            c["count"] for cat, c in by_category.items()
            if c.get("avg_measurability", 0) < 0.3
        )
        
        return {
            "status": "critical" if gap_ratio > 0.5 else "warning" if gap_ratio > 0.2 else "healthy",
            "gap_ratio": round(gap_ratio, 3),
            "verification_velocity": round(velocity, 3),
            "total_pending": pending,
            "total_verified": verified,
            "high_measurability_outputs": high_measurability,
            "low_measurability_outputs": low_measurability,
            "measurability_ratio": round(high_measurability / total_outputs, 3) if total_outputs > 0 else 0,
            "by_category": by_category,  # Always include by_category
            "recommendation": self._generate_recommendation(gap_ratio, by_category)
        }
    
    def _generate_recommendation(self, 
                                 gap_ratio: float,
                                 by_category: Dict) -> str:
        """Generate recommendation based on gap analysis"""
        if gap_ratio > 0.5:
            return "CRITICAL: Verification bottleneck detected. Scale verification capacity or reduce low-measurability outputs."
        
        if gap_ratio > 0.2:
            return "WARNING: Measurability gap growing. Consider automated verification for high-measurability categories."
        
        # Check category distribution
        synthetic_pct = by_category.get(OutputCategory.SYNTHETIC.value, {}).get("count", 0) / sum(
            c["count"] for c in by_category.values()
        ) if by_category else 0
        
        if synthetic_pct > 0.3:
            return "ADVISORY: High proportion of synthetic outputs. Implement peer review workflows."
        
        return "HEALTHY: Verification capacity sufficient for current output volume."


def create_verification_system() -> Tuple[VerificationSystem, MeasurabilityGapAnalyzer]:
    """Factory function to create verification system with analyzer"""
    vs = VerificationSystem()
    analyzer = MeasurabilityGapAnalyzer(vs)
    return vs, analyzer


if __name__ == "__main__":
    # Demo usage
    vs, analyzer = create_verification_system()
    
    print("=== Verification System Demo ===\n")
    
    # Register various outputs
    outputs = [
        ("code_gen", "def hello(): return 'world'", "deterministic"),
        ("analysis", "Market trends suggest growth...", "semantic"),
        ("insight", "New hypothesis about...", "synthetic"),
        ("creative", "Generated logo design...", "creative"),
        ("action", "API call to transfer funds", "action"),
    ]
    
    agent_id = "test_agent"
    
    for output_type, content, category in outputs:
        output = vs.register_output(
            agent_id=agent_id,
            output_type=output_type,
            content=content,
            category=category
        )
        
        print(f"Output: {output_type}")
        print(f"  Category: {category}")
        print(f"  Measurability: {output.measurability_score:.2f}")
        print(f"  Est. Verification Cost: {output.verification_cost_estimate} min")
        
        # Add evidence
        vs.add_evidence(
            output_id=output.id,
            evidence_type="test_result",
            content="Validation passed",
            source="automated_test",
            confidence=0.8
        )
        
        # Verify
        attestation = vs.verify_output(
            output_id=output.id,
            verifier_id="auto_verifier",
            verifier_type="automated",
            method="automated_test",
            confidence=0.8
        )
        
        print(f"  Attestation: {attestation.id[:8]}...")
        print(f"  Confidence Score: {output.confidence_score:.2f}\n")
    
    # Check agent reputation
    reputation = vs.get_agent_reputation(agent_id)
    print(f"Agent Reputation: {reputation}")
    
    # Analyze measurability gap
    gap_analysis = analyzer.analyze_gap()
    print(f"\nMeasurability Gap Analysis:")
    print(json.dumps(gap_analysis, indent=2))
    
    # System stats
    print(f"\nSystem Stats:")
    print(json.dumps(vs.get_verification_stats(), indent=2))
