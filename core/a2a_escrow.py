"""
Agent-to-Agent (A2A) Escrow & Transaction Protocol.

Based on research:
- AgentGram: Ed25519 crypto identity, reputation/AXP-based permissions
- AgentScope: A2A protocol support with message hub
- Ouroboros: Multi-model governance for transactions
- Enterprise need: 40% of AI agent projects fail due to architecture gaps

Implements secure agent transactions with:
1. Capability advertisement and discovery
2. Service request escrow (conditional execution)
3. Multi-agent negotiation and contracts
4. Reputation-weighted transaction verification
5. Attestation-based settlement
"""

from typing import Dict, List, Any, Optional, Callable, Set, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
import hashlib
import secrets
import json
import time
from collections import defaultdict
import uuid


class TransactionStatus(Enum):
    """Status of an A2A transaction."""
    PROPOSED = "proposed"           # Initial proposal sent
    NEGOTIATING = "negotiating"     # Terms being discussed
    ESCROWED = "escrowed"           # Funds/resources held in escrow
    EXECUTING = "executing"         # Service being performed
    VERIFYING = "verifying"         # Verification of completion
    COMPLETED = "completed"         # Successfully finished
    DISPUTED = "disputed"           # Conflict raised
    CANCELLED = "cancelled"         # Aborted before completion
    EXPIRED = "expired"             # Timed out


class CapabilityCategory(Enum):
    """Categories of agent capabilities/services."""
    COMPUTE = "compute"             # Processing, analysis
    DATA = "data"                   # Data retrieval, storage
    CODE = "code"                   # Code generation, review
    RESEARCH = "research"           # Information gathering
    CREATIVE = "creative"           # Content creation
    ORCHESTRATION = "orchestration"  # Task coordination
    VERIFICATION = "verification"   # Validation, testing
    COMMUNICATION = "communication" # External interaction


@dataclass
class Capability:
    """
    A capability that an agent advertises as available for hire.
    
    Inspired by AgentGram's semantic/vector search for agent discovery.
    """
    capability_id: str
    agent_id: str
    category: CapabilityCategory
    name: str
    description: str
    
    # Service terms
    estimated_duration_ms: int  # Expected time to complete
    min_reputation_required: float = 0.3  # Client must have this reputation
    
    # Capabilities as tags for semantic search
    tags: List[str] = field(default_factory=list)
    
    # Performance metrics (historical)
    total_requests: int = 0
    successful_completions: int = 0
    average_quality_score: float = 0.0
    
    # Availability
    is_available: bool = True
    max_concurrent_requests: int = 3
    current_requests: int = 0
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    
    def calculate_success_rate(self) -> float:
        """Calculate historical success rate."""
        if self.total_requests == 0:
            return 0.5  # Unknown - neutral
        return self.successful_completions / self.total_requests
    
    def can_accept_request(self) -> bool:
        """Check if capability can accept new request."""
        return self.is_available and self.current_requests < self.max_concurrent_requests
    
    def to_dict(self) -> Dict:
        return {
            "capability_id": self.capability_id,
            "agent_id": self.agent_id,
            "category": self.category.value,
            "name": self.name,
            "description": self.description,
            "estimated_duration_ms": self.estimated_duration_ms,
            "min_reputation_required": self.min_reputation_required,
            "tags": self.tags,
            "success_rate": round(self.calculate_success_rate(), 3),
            "avg_quality": round(self.average_quality_score, 3),
            "is_available": self.is_available,
            "available_slots": self.max_concurrent_requests - self.current_requests,
            "created_at": self.created_at
        }


@dataclass
class ServiceRequest:
    """
    A request for service from one agent to another.
    
    This is the proposal phase before escrow.
    """
    request_id: str
    requester_id: str  # Client agent
    provider_id: str   # Service provider agent
    capability_id: str
    
    # Request details
    task_description: str
    requirements: Dict[str, Any]  # Specific requirements
    
    # Terms proposed by requester
    proposed_payment: Dict[str, Any]  # Could be reputation, tokens, etc.
    deadline_ms: int  # Maximum time allowed
    
    # Negotiation
    negotiated_terms: Optional[Dict[str, Any]] = None
    negotiation_rounds: int = 0
    max_negotiation_rounds: int = 3
    
    # Status tracking
    status: TransactionStatus = TransactionStatus.PROPOSED
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    
    def __post_init__(self):
        if self.expires_at is None:
            self.expires_at = time.time() + (24 * 3600)  # 24 hour default
    
    def is_expired(self) -> bool:
        return time.time() > self.expires_at
    
    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "requester_id": self.requester_id,
            "provider_id": self.provider_id,
            "capability_id": self.capability_id,
            "task_description": self.task_description,
            "requirements": self.requirements,
            "proposed_payment": self.proposed_payment,
            "deadline_ms": self.deadline_ms,
            "negotiated_terms": self.negotiated_terms,
            "negotiation_rounds": self.negotiation_rounds,
            "status": self.status.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at
        }


@dataclass
class Escrow:
    """
    An escrow holding commitments from both parties.
    
    Neither party can unilaterally withdraw once escrowed.
    Requires attestation to release.
    """
    escrow_id: str
    request_id: str
    
    # Commitments
    client_commitment: Dict[str, Any]  # What client puts in escrow
    provider_commitment: Dict[str, Any]  # What provider commits
    
    # Status
    client_deposited: bool = False
    provider_deposited: bool = False
    
    # Attestation for release
    attestation_hash: Optional[str] = None
    attestation_signature: Optional[str] = None
    
    # Timestamps
    created_at: float = field(default_factory=time.time)
    deadline: float = field(default_factory=lambda: time.time() + 86400)
    released_at: Optional[float] = None
    
    def is_fully_funded(self) -> bool:
        return self.client_deposited and self.provider_deposited
    
    def can_release(self) -> bool:
        return self.is_fully_funded() and self.attestation_hash is not None
    
    def is_expired(self) -> bool:
        return time.time() > self.deadline and not self.can_release()


@dataclass
class Contract:
    """
    A finalized contract between two agents.
    
    Created after successful negotiation and escrow.
    """
    contract_id: str
    request_id: str
    escrow_id: str
    
    # Parties
    client_id: str
    provider_id: str
    capability_id: str
    
    # Final terms
    final_terms: Dict[str, Any]
    
    # Execution tracking
    deliverables: List[Dict[str, Any]] = field(default_factory=list)
    verification_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # Status
    status: TransactionStatus = TransactionStatus.ESCROWED
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    
    # Quality
    quality_score: Optional[float] = None  # 0.0 to 1.0
    
    def to_dict(self) -> Dict:
        return {
            "contract_id": self.contract_id,
            "client_id": self.client_id,
            "provider_id": self.provider_id,
            "capability_id": self.capability_id,
            "final_terms": self.final_terms,
            "status": self.status.value,
            "quality_score": self.quality_score,
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }


@dataclass
class Attestation:
    """
    Cryptographic attestation of transaction completion.
    
    Multiple verifiers can provide attestations for high-value transactions.
    """
    attestation_id: str
    contract_id: str
    verifier_id: str
    
    # What is being attested
    claim: str  # Description of verified completion
    evidence_hash: str  # Hash of evidence data
    
    # Verification
    verification_score: float  # 0.0 to 1.0, confidence in attestation
    timestamp: float = field(default_factory=time.time)
    
    # Signature (simplified)
    signature: Optional[str] = None
    
    def sign(self, private_key: str):
        """Create attestation signature."""
        data = f"{self.contract_id}:{self.claim}:{self.evidence_hash}:{self.timestamp}"
        self.signature = hashlib.sha256((data + private_key).encode()).hexdigest()[:32]
        return self.signature


class A2AProtocol:
    """
    Agent-to-Agent Protocol for secure transactions and escrow.
    
    Handles:
    - Capability advertisement and discovery
    - Service negotiation
    - Escrow management
    - Contract execution tracking
    - Attestation-based settlement
    """
    
    def __init__(self):
        # Capability registry (semantic search enabled)
        self.capabilities: Dict[str, Capability] = {}
        self.agent_capabilities: Dict[str, Set[str]] = defaultdict(set)
        self.capability_index: Dict[CapabilityCategory, Set[str]] = defaultdict(set)
        
        # Transaction tracking
        self.requests: Dict[str, ServiceRequest] = {}
        self.escrows: Dict[str, Escrow] = {}
        self.contracts: Dict[str, Contract] = {}
        
        # Attestations
        self.attestations: Dict[str, List[Attestation]] = defaultdict(list)
        
        # Reputation integration (reference to external system)
        self.reputation_callback: Optional[Callable[[str], float]] = None
        
        # Dispute resolution
        self.disputes: Dict[str, Dict] = {}
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "successful_contracts": 0,
            "disputed_contracts": 0,
            "total_escrow_value": 0.0,
            "avg_negotiation_rounds": 0.0
        }
    
    def set_reputation_callback(self, callback: Callable[[str], float]):
        """Set callback to query agent reputation."""
        self.reputation_callback = callback
    
    def get_agent_reputation(self, agent_id: str) -> float:
        """Get agent reputation (uses callback or default)."""
        if self.reputation_callback:
            return self.reputation_callback(agent_id)
        return 0.5  # Default neutral
    
    # ==================== Capability Management ====================
    
    def advertise_capability(
        self,
        agent_id: str,
        category: CapabilityCategory,
        name: str,
        description: str,
        estimated_duration_ms: int,
        min_reputation_required: float = 0.3,
        tags: List[str] = None,
        max_concurrent: int = 3
    ) -> Capability:
        """
        Advertise a capability that other agents can request.
        
        Returns the created Capability.
        """
        capability_id = f"cap_{uuid.uuid4().hex[:12]}"
        
        cap = Capability(
            capability_id=capability_id,
            agent_id=agent_id,
            category=category,
            name=name,
            description=description,
            estimated_duration_ms=estimated_duration_ms,
            min_reputation_required=min_reputation_required,
            tags=tags or [],
            max_concurrent_requests=max_concurrent
        )
        
        self.capabilities[capability_id] = cap
        self.agent_capabilities[agent_id].add(capability_id)
        self.capability_index[category].add(capability_id)
        
        print(f"📢 Capability advertised: '{name}' by {agent_id}")
        print(f"   Category: {category.value}, Tags: {tags or []}")
        
        return cap
    
    def discover_capabilities(
        self,
        category: Optional[CapabilityCategory] = None,
        tags: List[str] = None,
        min_success_rate: float = 0.0,
        available_only: bool = True,
        limit: int = 10
    ) -> List[Capability]:
        """
        Discover capabilities matching criteria.
        
        Semantic search by category and tags.
        """
        candidates = set()
        
        # Filter by category
        if category:
            candidates = self.capability_index[category].copy()
        else:
            candidates = set(self.capabilities.keys())
        
        results = []
        for cap_id in candidates:
            cap = self.capabilities.get(cap_id)
            if not cap:
                continue
            
            # Filter by availability
            if available_only and not cap.can_accept_request():
                continue
            
            # Filter by success rate
            if cap.calculate_success_rate() < min_success_rate:
                continue
            
            # Tag matching (at least one required tag)
            if tags:
                if not any(tag in cap.tags for tag in tags):
                    continue
            
            results.append(cap)
        
        # Sort by: success rate, then avg quality
        results.sort(key=lambda c: (c.calculate_success_rate(), c.average_quality_score), reverse=True)
        
        return results[:limit]
    
    def get_agent_capabilities(self, agent_id: str) -> List[Capability]:
        """Get all capabilities advertised by an agent."""
        cap_ids = self.agent_capabilities.get(agent_id, set())
        return [self.capabilities[cid] for cid in cap_ids if cid in self.capabilities]
    
    # ==================== Request & Negotiation ====================
    
    def request_service(
        self,
        requester_id: str,
        capability_id: str,
        task_description: str,
        requirements: Dict[str, Any] = None,
        proposed_payment: Dict[str, Any] = None,
        deadline_ms: int = 3600000  # 1 hour default
    ) -> Optional[ServiceRequest]:
        """
        Request a service from a capability provider.
        
        Creates a service request and initiates negotiation.
        """
        # Verify capability exists
        if capability_id not in self.capabilities:
            print(f"❌ Capability {capability_id} not found")
            return None
        
        cap = self.capabilities[capability_id]
        provider_id = cap.agent_id
        
        # Check reputation requirements
        requester_rep = self.get_agent_reputation(requester_id)
        if requester_rep < cap.min_reputation_required:
            print(f"🚫 Requester reputation {requester_rep:.2f} below requirement {cap.min_reputation_required}")
            return None
        
        # Create request
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        request = ServiceRequest(
            request_id=request_id,
            requester_id=requester_id,
            provider_id=provider_id,
            capability_id=capability_id,
            task_description=task_description,
            requirements=requirements or {},
            proposed_payment=proposed_payment or {"type": "reputation", "amount": 0.1},
            deadline_ms=deadline_ms
        )
        
        self.requests[request_id] = request
        self.stats["total_requests"] += 1
        cap.current_requests += 1
        
        print(f"📨 Service requested: '{task_description[:50]}...'")
        print(f"   Requester: {requester_id} → Provider: {provider_id}")
        print(f"   Reputation: {requester_rep:.2f} (required: {cap.min_reputation_required})")
        
        return request
    
    def negotiate_terms(
        self,
        request_id: str,
        counter_terms: Dict[str, Any],
        accepted: bool = False
    ) -> bool:
        """
        Negotiate terms for a service request.
        
        Can be called by either party to propose counter-terms or accept.
        """
        if request_id not in self.requests:
            return False
        
        request = self.requests[request_id]
        
        if request.status not in [TransactionStatus.PROPOSED, TransactionStatus.NEGOTIATING]:
            print(f"❌ Request {request_id} not in negotiable state")
            return False
        
        if request.is_expired():
            request.status = TransactionStatus.EXPIRED
            return False
        
        if request.negotiation_rounds >= request.max_negotiation_rounds:
            print(f"🚫 Max negotiation rounds ({request.max_negotiation_rounds}) reached")
            return False
        
        if accepted:
            # Finalize terms
            request.negotiated_terms = counter_terms if counter_terms else request.proposed_payment
            request.status = TransactionStatus.NEGOTIATING  # Ready for escrow
            print(f"✅ Terms accepted for {request_id}")
            return True
        else:
            # Propose counter-terms
            request.negotiated_terms = counter_terms
            request.negotiation_rounds += 1
            request.status = TransactionStatus.NEGOTIATING
            print(f"🔄 Counter-terms proposed (round {request.negotiation_rounds})")
            return True
    
    # ==================== Escrow Management ====================
    
    def create_escrow(self, request_id: str) -> Optional[Escrow]:
        """
        Create escrow for an accepted request.
        
        Both parties must deposit their commitments.
        """
        if request_id not in self.requests:
            return None
        
        request = self.requests[request_id]
        
        if request.status != TransactionStatus.NEGOTIATING or not request.negotiated_terms:
            print(f"❌ Request not ready for escrow")
            return None
        
        escrow_id = f"esc_{uuid.uuid4().hex[:12]}"
        
        escrow = Escrow(
            escrow_id=escrow_id,
            request_id=request_id,
            client_commitment=request.negotiated_terms.get("client_commitment", {"type": "reputation"}),
            provider_commitment={"service": request.task_description, "deadline": request.deadline_ms},
            deadline=time.time() + (request.deadline_ms / 1000) + 300  # 5 min buffer
        )
        
        self.escrows[escrow_id] = escrow
        request.status = TransactionStatus.ESCROWED
        
        print(f"🔒 Escrow created: {escrow_id}")
        print(f"   Client: {request.requester_id}, Provider: {request.provider_id}")
        
        return escrow
    
    def deposit_to_escrow(
        self,
        escrow_id: str,
        party: str,  # "client" or "provider"
        signature: str
    ) -> bool:
        """Deposit commitment to escrow."""
        if escrow_id not in self.escrows:
            return False
        
        escrow = self.escrows[escrow_id]
        
        if party == "client":
            escrow.client_deposited = True
            print(f"💰 Client deposited to escrow {escrow_id}")
        elif party == "provider":
            escrow.provider_deposited = True
            print(f"💰 Provider deposited to escrow {escrow_id}")
        else:
            return False
        
        return True
    
    def create_contract(self, escrow_id: str) -> Optional[Contract]:
        """Create contract once escrow is fully funded."""
        if escrow_id not in self.escrows:
            return None
        
        escrow = self.escrows[escrow_id]
        
        if not escrow.is_fully_funded():
            print(f"⏳ Escrow {escrow_id} not fully funded")
            return None
        
        request = self.requests.get(escrow.request_id)
        if not request:
            return None
        
        contract_id = f"ctr_{uuid.uuid4().hex[:12]}"
        
        contract = Contract(
            contract_id=contract_id,
            request_id=escrow.request_id,
            escrow_id=escrow_id,
            client_id=request.requester_id,
            provider_id=request.provider_id,
            capability_id=request.capability_id,
            final_terms=request.negotiated_terms,
            status=TransactionStatus.ESCROWED
        )
        
        self.contracts[contract_id] = contract
        
        print(f"📜 Contract created: {contract_id}")
        print(f"   Executing: {request.task_description[:40]}...")
        
        return contract
    
    def start_execution(self, contract_id: str) -> bool:
        """
        Start contract execution.
        
        Transitions contract from ESCROWED to EXECUTING.
        """
        if contract_id not in self.contracts:
            return False
        
        contract = self.contracts[contract_id]
        
        if contract.status != TransactionStatus.ESCROWED:
            return False
        
        contract.status = TransactionStatus.EXECUTING
        print(f"▶️  Execution started for contract {contract_id}")
        
        return True
    
    # ==================== Verification & Settlement ====================
    
    def submit_deliverable(
        self,
        contract_id: str,
        deliverable: Dict[str, Any],
        evidence: str  # Hash of evidence
    ) -> bool:
        """Submit deliverable for verification."""
        if contract_id not in self.contracts:
            return False
        
        contract = self.contracts[contract_id]
        
        if contract.status != TransactionStatus.EXECUTING:
            return False
        
        contract.deliverables.append({
            "data": deliverable,
            "evidence_hash": evidence,
            "submitted_at": time.time()
        })
        
        contract.status = TransactionStatus.VERIFYING
        print(f"📦 Deliverable submitted for contract {contract_id}")
        
        return True
    
    def create_attestation(
        self,
        contract_id: str,
        verifier_id: str,
        claim: str,
        evidence_hash: str,
        verification_score: float,
        private_key: str
    ) -> Attestation:
        """
        Create cryptographic attestation of contract completion.
        
        Multiple attestations increase confidence for high-value contracts.
        """
        attestation_id = f"att_{uuid.uuid4().hex[:12]}"
        
        attestation = Attestation(
            attestation_id=attestation_id,
            contract_id=contract_id,
            verifier_id=verifier_id,
            claim=claim,
            evidence_hash=evidence_hash,
            verification_score=verification_score
        )
        
        attestation.sign(private_key)
        
        self.attestations[contract_id].append(attestation)
        
        print(f"✍️  Attestation created by {verifier_id}: {claim[:50]}...")
        print(f"   Score: {verification_score:.2f}, Contract: {contract_id}")
        
        return attestation
    
    def release_escrow(self, contract_id: str) -> bool:
        """
        Release escrow based on attestations.
        
        Requires sufficient attestation confidence.
        """
        if contract_id not in self.contracts:
            return False
        
        contract = self.contracts[contract_id]
        escrow = self.escrows.get(contract.escrow_id)
        
        if not escrow:
            return False
        
        # Check attestations
        atts = self.attestations.get(contract_id, [])
        
        if len(atts) == 0:
            print(f"⏳ No attestations for contract {contract_id}")
            return False
        
        # Calculate weighted confidence
        total_confidence = sum(att.verification_score for att in atts)
        
        # Need at least 0.5 total confidence (could be 1 strong or multiple weak)
        if total_confidence < 0.5:
            print(f"⏳ Insufficient attestation confidence: {total_confidence:.2f}")
            return False
        
        # Release escrow
        escrow.released_at = time.time()
        escrow.attestation_hash = hashlib.sha256(
            json.dumps([att.signature for att in atts]).encode()
        ).hexdigest()[:32]
        
        contract.status = TransactionStatus.COMPLETED
        contract.completed_at = time.time()
        
        # Calculate quality score from attestations
        contract.quality_score = sum(att.verification_score for att in atts) / len(atts)
        
        # Update capability stats
        cap = self.capabilities.get(contract.capability_id)
        if cap:
            cap.successful_completions += 1
            cap.average_quality_score = (
                (cap.average_quality_score * (cap.successful_completions - 1)) +
                contract.quality_score
            ) / cap.successful_completions
        
        self.stats["successful_contracts"] += 1
        
        print(f"✅ Escrow released for contract {contract_id}")
        print(f"   Quality score: {contract.quality_score:.2f}")
        print(f"   Attestations: {len(atts)}, Total confidence: {total_confidence:.2f}")
        
        return True
    
    # ==================== Dispute Resolution ====================
    
    def raise_dispute(
        self,
        contract_id: str,
        raised_by: str,
        reason: str
    ) -> bool:
        """Raise a dispute for contract resolution."""
        if contract_id not in self.contracts:
            return False
        
        contract = self.contracts[contract_id]
        contract.status = TransactionStatus.DISPUTED
        
        self.disputes[contract_id] = {
            "raised_by": raised_by,
            "reason": reason,
            "raised_at": time.time(),
            "status": "pending"
        }
        
        self.stats["disputed_contracts"] += 1
        
        print(f"⚠️  DISPUTE raised for contract {contract_id}")
        print(f"   By: {raised_by}, Reason: {reason}")
        
        return True
    
    def resolve_dispute(
        self,
        contract_id: str,
        resolution: str,  # "client_wins", "provider_wins", "split", "cancel"
        arbiter_id: str
    ) -> bool:
        """Resolve a dispute with arbiter decision."""
        if contract_id not in self.disputes:
            return False
        
        dispute = self.disputes[contract_id]
        dispute["resolution"] = resolution
        dispute["resolved_by"] = arbiter_id
        dispute["resolved_at"] = time.time()
        dispute["status"] = "resolved"
        
        contract = self.contracts[contract_id]
        
        if resolution == "client_wins":
            contract.status = TransactionStatus.CANCELLED
            print(f"🏛️  Dispute resolved: Client wins (contract {contract_id})")
        elif resolution == "provider_wins":
            contract.status = TransactionStatus.COMPLETED
            contract.quality_score = 0.5  # Neutral
            print(f"🏛️  Dispute resolved: Provider wins (contract {contract_id})")
        else:
            contract.status = TransactionStatus.CANCELLED
            print(f"🏛️  Dispute resolved: {resolution} (contract {contract_id})")
        
        return True
    
    # ==================== Analytics & Reporting ====================
    
    def get_protocol_stats(self) -> Dict:
        """Get A2A protocol statistics."""
        active_contracts = sum(
            1 for c in self.contracts.values()
            if c.status in [TransactionStatus.EXECUTING, TransactionStatus.VERIFYING]
        )
        
        total_negotiations = sum(
            r.negotiation_rounds for r in self.requests.values()
        )
        
        avg_negotiations = (
            total_negotiations / len(self.requests) if self.requests else 0
        )
        
        return {
            **self.stats,
            "active_contracts": active_contracts,
            "total_capabilities": len(self.capabilities),
            "total_escrows": len(self.escrows),
            "avg_negotiation_rounds": round(avg_negotiations, 2),
            "success_rate": (
                self.stats["successful_contracts"] / max(1, len(self.contracts))
            ),
            "pending_disputes": sum(
                1 for d in self.disputes.values() if d["status"] == "pending"
            )
        }
    
    def get_agent_transaction_history(self, agent_id: str) -> Dict:
        """Get transaction history for an agent."""
        as_client = [
            c.to_dict() for c in self.contracts.values()
            if c.client_id == agent_id
        ]
        as_provider = [
            c.to_dict() for c in self.contracts.values()
            if c.provider_id == agent_id
        ]
        
        return {
            "agent_id": agent_id,
            "contracts_as_client": as_client,
            "contracts_as_provider": as_provider,
            "total_transactions": len(as_client) + len(as_provider),
            "avg_quality_as_provider": (
                sum(c.quality_score or 0 for c in self.contracts.values()
                    if c.provider_id == agent_id) / max(1, len(as_provider))
            )
        }


def demo_a2a_protocol():
    """Demonstrate A2A protocol with realistic scenario."""
    print("=" * 70)
    print("🔐 AGENT-TO-AGENT (A2A) ESCROW PROTOCOL DEMO")
    print("=" * 70)
    
    # Create protocol
    a2a = A2AProtocol()
    
    # Set reputation callback (mock)
    agent_reputations = {
        "Alpha": 0.85,
        "Beta": 0.75,
        "Gamma": 0.60,
        "Delta": 0.40,
        "Verifier": 0.90
    }
    a2a.set_reputation_callback(lambda aid: agent_reputations.get(aid, 0.5))
    
    print("\n" + "-" * 70)
    print("📢 PHASE 1: Capability Advertisement")
    print("-" * 70)
    
    # Agents advertise capabilities
    cap1 = a2a.advertise_capability(
        agent_id="Beta",
        category=CapabilityCategory.CODE,
        name="Code Review & Analysis",
        description="Expert code review with security and performance analysis",
        estimated_duration_ms=300000,  # 5 min
        min_reputation_required=0.5,
        tags=["code", "review", "security", "python"]
    )
    
    cap2 = a2a.advertise_capability(
        agent_id="Gamma",
        category=CapabilityCategory.RESEARCH,
        name="Web Research & Synthesis",
        description="Deep web research with source verification",
        estimated_duration_ms=600000,  # 10 min
        min_reputation_required=0.4,
        tags=["research", "web", "synthesis", "verification"]
    )
    
    cap3 = a2a.advertise_capability(
        agent_id="Delta",
        category=CapabilityCategory.CODE,
        name="Quick Script Generation",
        description="Fast utility script generation",
        estimated_duration_ms=120000,  # 2 min
        min_reputation_required=0.3,
        tags=["code", "script", "automation"]
    )
    
    print("\n" + "-" * 70)
    print("🔍 PHASE 2: Capability Discovery")
    print("-" * 70)
    
    # Alpha discovers capabilities
    results = a2a.discover_capabilities(
        category=CapabilityCategory.CODE,
        tags=["review", "security"],
        min_success_rate=0.0,
        available_only=True
    )
    
    print(f"\nFound {len(results)} matching capabilities:")
    for cap in results:
        print(f"  - {cap.name} by {cap.agent_id} (success rate: {cap.calculate_success_rate():.1%})")
    
    print("\n" + "-" * 70)
    print("📨 PHASE 3: Service Request & Negotiation")
    print("-" * 70)
    
    # Alpha requests service from Beta
    request = a2a.request_service(
        requester_id="Alpha",
        capability_id=cap1.capability_id,
        task_description="Review my agent communication module for security vulnerabilities",
        requirements={
            "language": "python",
            "focus_areas": ["security", "performance"],
            "deliverable": "report"
        },
        proposed_payment={"type": "reputation", "amount": 0.1},
        deadline_ms=600000  # 10 min
    )
    
    if request:
        # Beta proposes counter-terms (shorter deadline)
        a2a.negotiate_terms(
            request_id=request.request_id,
            counter_terms={
                "deadline_ms": 300000,  # 5 min
                "payment": {"type": "reputation", "amount": 0.15},
                "priority": "high"
            },
            accepted=False
        )
        
        # Alpha accepts
        a2a.negotiate_terms(
            request_id=request.request_id,
            counter_terms={
                "client_commitment": {"reputation": 0.15},
                "deadline_ms": 300000,
                "payment": {"type": "reputation", "amount": 0.15}
            },
            accepted=True
        )
    
    print("\n" + "-" * 70)
    print("🔒 PHASE 4: Escrow & Contract")
    print("-" * 70)
    
    if request:
        # Create escrow
        escrow = a2a.create_escrow(request.request_id)
        
        if escrow:
            # Both parties deposit
            a2a.deposit_to_escrow(escrow.escrow_id, "client", "alpha_sig_123")
            a2a.deposit_to_escrow(escrow.escrow_id, "provider", "beta_sig_456")
            
            # Create contract
            contract = a2a.create_contract(escrow.escrow_id)
            
            print("\n" + "-" * 70)
            print("📦 PHASE 5: Execution & Verification")
            print("-" * 70)
            
            if contract:
                # Transition to executing
                a2a.start_execution(contract.contract_id)
                
                # Beta completes work and submits
                a2a.submit_deliverable(
                    contract_id=contract.contract_id,
                    deliverable={
                        "report": "Security analysis complete: 2 minor issues found",
                        "issues": ["Unused import", "Weak exception handling"]
                    },
                    evidence=hashlib.sha256(b"deliverable_data").hexdigest()
                )
                
                # Verifier attests completion
                a2a.create_attestation(
                    contract_id=contract.contract_id,
                    verifier_id="Verifier",
                    claim="Code review completed satisfactorily. 2 issues identified and documented.",
                    evidence_hash=hashlib.sha256(b"verification_data").hexdigest(),
                    verification_score=0.85,
                    private_key="verifier_key_789"
                )
                
                # Release escrow
                a2a.release_escrow(contract.contract_id)
    
    print("\n" + "-" * 70)
    print("📊 PHASE 6: Statistics")
    print("-" * 70)
    
    stats = a2a.get_protocol_stats()
    print("\nA2A Protocol Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Transaction history
    print("\n" + "-" * 70)
    print("📜 Agent Transaction Histories")
    print("-" * 70)
    
    for agent_id in ["Alpha", "Beta"]:
        history = a2a.get_agent_transaction_history(agent_id)
        print(f"\n{agent_id}:")
        print(f"  Total transactions: {history['total_transactions']}")
        print(f"  As client: {len(history['contracts_as_client'])}")
        print(f"  As provider: {len(history['contracts_as_provider'])}")
    
    print("\n" + "=" * 70)
    print("✅ A2A PROTOCOL DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    demo_a2a_protocol()
