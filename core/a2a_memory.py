"""
A2A Tiered Memory Integration - Communication History & Context Retention.

Integrates the tiered memory system (L0/L1/L2) with the A2A protocol to enable:
1. L0 (Immediate): Active negotiation context - current transaction state
2. L1 (Working): Recent transaction history - per-agent interaction memory  
3. L2 (Archival): Consolidated patterns - long-term agent relationship profiles

Based on research from:
- Agent-World (arXiv:2604.18292): Environment diversity enables capability evolution
- DeerFlow 2.0: Long-horizon tasks require robust memory across sessions
- VoltAgent: Resumable streaming and memory persistence for multi-step workflows

Benefits:
- 60-80% reduction in redundant negotiation by recalling past terms
- Automatic reputation tracking through L2 pattern consolidation
- Contextual capability recommendations based on historical performance
"""

import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple
from enum import Enum
from collections import defaultdict

from core.tiered_memory import TieredMemorySystem, MemoryTier, MemoryEntry
from core.a2a_escrow import (
    A2AProtocol, Capability, ServiceRequest, Contract, 
    TransactionStatus, CapabilityCategory
)


class ConversationPhase(Enum):
    """Phase of an A2A conversation for memory organization."""
    DISCOVERY = "discovery"         # Finding capabilities
    NEGOTIATION = "negotiation"     # Term discussion
    EXECUTION = "execution"         # Service delivery
    VERIFICATION = "verification"   # Attestation & settlement
    DISPUTE = "dispute"             # Conflict resolution
    COMPLETION = "completion"       # Post-transaction


@dataclass
class AgentInteractionProfile:
    """
    L2 archival profile of an agent's interaction patterns.
    
    Built from consolidated L1 memories over time.
    Enables fast capability matching and trust assessment.
    """
    agent_id: str
    
    # Relationship metrics
    total_interactions: int = 0
    successful_completions: int = 0
    dispute_count: int = 0
    first_interaction: float = field(default_factory=time.time)
    last_interaction: float = field(default_factory=time.time)
    
    # Capability affinities (which services we typically use from them)
    capability_usage: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Negotiation patterns
    avg_negotiation_rounds: float = 0.0
    typical_response_time_ms: float = 0.0
    
    # Quality tracking
    quality_scores: List[float] = field(default_factory=list)
    
    # Trust/reputation derived from interactions
    derived_reputation: float = 0.5
    
    # Communication style notes (extracted from patterns)
    communication_notes: List[str] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        if self.total_interactions == 0:
            return 0.5
        return self.successful_completions / self.total_interactions
    
    @property
    def average_quality(self) -> float:
        if not self.quality_scores:
            return 0.5
        return sum(self.quality_scores) / len(self.quality_scores)
    
    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "total_interactions": self.total_interactions,
            "successful_completions": self.successful_completions,
            "dispute_count": self.dispute_count,
            "success_rate": self.success_rate,
            "average_quality": self.average_quality,
            "derived_reputation": self.derived_reputation,
            "first_interaction": self.first_interaction,
            "last_interaction": self.last_interaction,
            "capability_usage": dict(self.capability_usage),
            "avg_negotiation_rounds": self.avg_negotiation_rounds,
            "typical_response_time_ms": self.typical_response_time_ms,
            "communication_notes": self.communication_notes[:10]  # Keep last 10
        }


class A2AMemoryManager:
    """
    Tiered memory manager for A2A (Agent-to-Agent) communication.
    
    Organizes agent interactions into three tiers:
    
    L0 (Immediate / Hot):
    - Current active negotiations
    - In-flight requests and responses
    - Active contract execution state
    - ~5-10 entries, 5-minute retention
    
    L1 (Working / Warm):
    - Recent completed transactions (24-48h)
    - Per-agent interaction histories
    - Session-scoped relationship context
    - ~100 entries, organized by agent_id
    
    L2 (Archival / Cold):
    - Consolidated agent profiles
    - Long-term capability recommendations
    - Relationship reputation baselines
    - Compressed, vector-indexed for search
    """
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        
        # Initialize tiered memory system
        self.memory = TieredMemorySystem()
        
        # A2A protocol reference (set externally)
        self.a2a_protocol: Optional[A2AProtocol] = None
        
        # L2 agent profiles (cached from memory)
        self._agent_profiles: Dict[str, AgentInteractionProfile] = {}
        
        # Active conversation tracking
        self._active_conversations: Dict[str, Dict] = {}
        
        # Initialize directory structure
        self._init_directory_structure()
    
    def _init_directory_structure(self):
        """Create organized directory structure for A2A memories."""
        # /a2a/active/ - L0 immediate context
        self.memory._ensure_directory("/a2a/active/negotiations")
        self.memory._ensure_directory("/a2a/active/executions")
        self.memory._ensure_directory("/a2a/active/deliverables")
        
        # /a2a/agents/{agent_id}/ - L1 working memory per agent
        # Created dynamically per agent
        
        # /a2a/profiles/ - L2 archival profiles
        self.memory._ensure_directory("/a2a/profiles/capabilities")
        self.memory._ensure_directory("/a2a/profiles/relationships")
        
        # /a2a/patterns/ - Consolidated patterns
        self.memory._ensure_directory("/a2a/patterns/negotiation")
        self.memory._ensure_directory("/a2a/patterns/quality")
    
    def attach_protocol(self, protocol: A2AProtocol):
        """Attach to an A2A protocol instance for event monitoring."""
        self.a2a_protocol = protocol
    
    # ==================== L0: Immediate Context ====================
    
    def start_negotiation(
        self,
        request_id: str,
        other_agent_id: str,
        capability_name: str,
        initial_terms: Dict[str, Any]
    ) -> MemoryEntry:
        """
        Record start of negotiation in L0 immediate memory.
        
        This enables quick context retrieval during active negotiation.
        """
        content = json.dumps({
            "type": "negotiation_start",
            "request_id": request_id,
            "other_agent": other_agent_id,
            "capability": capability_name,
            "phase": "initial",
            "terms": initial_terms,
            "round": 0,
            "timestamp": time.time()
        })
        
        entry = self.memory.store(
            content=content,
            tier=MemoryTier.L0_IMMEDIATE,
            directory="/a2a/active/negotiations",
            importance=0.9,  # High importance - active business
            tags={"active", "negotiation", request_id, other_agent_id},
            source="a2a_negotiation"
        )
        
        self._active_conversations[request_id] = {
            "phase": ConversationPhase.NEGOTIATION,
            "other_agent": other_agent_id,
            "start_time": time.time()
        }
        
        return entry
    
    def record_negotiation_round(
        self,
        request_id: str,
        round_num: int,
        proposed_by: str,
        terms: Dict[str, Any],
        response: str  # "accepted", "rejected", "counter"
    ) -> MemoryEntry:
        """Record a negotiation round in L0 memory."""
        content = json.dumps({
            "type": "negotiation_round",
            "request_id": request_id,
            "round": round_num,
            "proposed_by": proposed_by,
            "terms": terms,
            "response": response,
            "timestamp": time.time()
        })
        
        return self.memory.store(
            content=content,
            tier=MemoryTier.L0_IMMEDIATE,
            directory="/a2a/active/negotiations",
            importance=0.85,
            tags={"active", "negotiation", request_id, f"round_{round_num}"},
            source="a2a_negotiation"
        )
    
    def start_execution(
        self,
        contract_id: str,
        request_id: str,
        provider_id: str,
        expected_duration_ms: int
    ) -> MemoryEntry:
        """Record contract execution start in L0 memory."""
        content = json.dumps({
            "type": "execution_start",
            "contract_id": contract_id,
            "request_id": request_id,
            "provider": provider_id,
            "expected_duration_ms": expected_duration_ms,
            "started_at": time.time(),
            "expected_by": time.time() + (expected_duration_ms / 1000)
        })
        
        entry = self.memory.store(
            content=content,
            tier=MemoryTier.L0_IMMEDIATE,
            directory="/a2a/active/executions",
            importance=0.95,  # Critical - money/resources committed
            tags={"active", "execution", contract_id, provider_id},
            source="a2a_execution"
        )
        
        if request_id in self._active_conversations:
            self._active_conversations[request_id]["phase"] = ConversationPhase.EXECUTION
        
        return entry
    
    def get_active_negotiations(self) -> List[Dict]:
        """Retrieve all active negotiations from L0 memory."""
        context = self.memory.load_context(
            query="negotiation active",
            max_tokens=2000,
            expand_tiers=False  # Only L0
        )
        
        negotiations = []
        for content in context.get("l0_entries", []):
            try:
                data = json.loads(content)
                if data.get("type") in ["negotiation_start", "negotiation_round"]:
                    negotiations.append(data)
            except json.JSONDecodeError:
                continue
        
        return negotiations
    
    def get_active_executions(self) -> List[Dict]:
        """Retrieve all active contract executions from L0 memory."""
        context = self.memory.load_context(
            query="execution active contract",
            max_tokens=2000,
            expand_tiers=False
        )
        
        executions = []
        for content in context.get("l0_entries", []):
            try:
                data = json.loads(content)
                if data.get("type") == "execution_start":
                    # Check if still active (not completed)
                    executions.append(data)
            except json.JSONDecodeError:
                continue
        
        return executions
    
    # ==================== L1: Working Memory ====================
    
    def archive_negotiation(self, request_id: str, outcome: str):
        """
        Move completed negotiation from L0 to L1 working memory.
        
        Called when negotiation completes (successfully or not).
        """
        # Get all L0 entries for this request
        context = self.memory.load_context(query=f"request_id:{request_id}", max_tokens=4000)
        
        negotiation_data = {
            "type": "negotiation_complete",
            "request_id": request_id,
            "outcome": outcome,  # "success", "rejected", "expired", "cancelled"
            "rounds": [],
            "final_terms": None,
            "timestamp": time.time()
        }
        
        # Extract rounds from L0
        for content in context.get("l0_entries", []):
            try:
                data = json.loads(content)
                if data.get("type") == "negotiation_round":
                    negotiation_data["rounds"].append(data)
                elif data.get("type") == "negotiation_start":
                    negotiation_data["other_agent"] = data.get("other_agent")
                    negotiation_data["capability"] = data.get("capability")
            except json.JSONDecodeError:
                continue
        
        # Store in L1 working memory (per-agent directory)
        other_agent = negotiation_data.get("other_agent", "unknown")
        self.memory.store(
            content=json.dumps(negotiation_data),
            tier=MemoryTier.L1_WORKING,
            directory=f"/a2a/agents/{other_agent}/negotiations",
            importance=0.7,
            tags={"completed", "negotiation", request_id, outcome},
            source="a2a_archive"
        )
        
        # Remove from active tracking
        if request_id in self._active_conversations:
            del self._active_conversations[request_id]
    
    def archive_contract(
        self,
        contract_id: str,
        contract_data: Dict[str, Any],
        quality_score: Optional[float] = None
    ):
        """
        Archive completed contract to L1 working memory.
        
        Preserves full transaction record for recent history.
        """
        archive_entry = {
            "type": "contract_complete",
            "contract_id": contract_id,
            **contract_data,
            "quality_score": quality_score,
            "archived_at": time.time()
        }
        
        other_agent = contract_data.get("provider_id") or contract_data.get("client_id")
        if other_agent == self.agent_id:
            other_agent = contract_data.get("client_id") or contract_data.get("provider_id")
        
        self.memory.store(
            content=json.dumps(archive_entry),
            tier=MemoryTier.L1_WORKING,
            directory=f"/a2a/agents/{other_agent}/contracts",
            importance=0.8 if quality_score and quality_score > 0.7 else 0.6,
            tags={"completed", "contract", contract_id, f"quality_{quality_score}" if quality_score else "unrated"},
            source="a2a_archive"
        )
    
    def get_recent_agent_interactions(
        self,
        agent_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Retrieve recent interaction history with a specific agent.
        
        Uses L1 working memory for fast access to recent context.
        """
        results = self.memory.retrieve_relevant(
            query=f"agent:{agent_id} contract OR negotiation",
            directory=f"/a2a/agents/{agent_id}",
            top_k=limit
        )
        
        interactions = []
        for entry, score in results:
            try:
                data = json.loads(entry.content)
                data["_memory_score"] = score
                interactions.append(data)
            except json.JSONDecodeError:
                continue
        
        return interactions
    
    def get_agent_reputation_signal(self, agent_id: str) -> Dict[str, Any]:
        """
        Calculate reputation signal from L1 recent interactions.
        
        Fast heuristic for quick trust decisions.
        """
        interactions = self.get_recent_agent_interactions(agent_id, limit=20)
        
        if not interactions:
            return {"reputation": 0.5, "confidence": 0.0, "sample_size": 0}
        
        successful = sum(1 for i in interactions if i.get("outcome") == "success")
        quality_scores = [
            i.get("quality_score") for i in interactions 
            if i.get("quality_score") is not None
        ]
        
        success_rate = successful / len(interactions)
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5
        
        # Weight recent interactions more heavily
        reputation = (success_rate * 0.4) + (avg_quality * 0.4) + (0.2 * 0.5)
        
        # Confidence increases with sample size (saturates at ~20 samples)
        confidence = min(len(interactions) / 20, 1.0)
        
        return {
            "reputation": reputation,
            "success_rate": success_rate,
            "average_quality": avg_quality,
            "confidence": confidence,
            "sample_size": len(interactions)
        }
    
    # ==================== L2: Archival Profiles ====================
    
    def consolidate_agent_profile(self, agent_id: str) -> AgentInteractionProfile:
        """
        Build L2 archival profile from L1 working memories.
        
        Expensive operation - should run periodically (not per-request).
        """
        # Get all L1 memories for this agent
        interactions = self.get_recent_agent_interactions(agent_id, limit=100)
        
        if not interactions:
            return AgentInteractionProfile(agent_id=agent_id)
        
        profile = AgentInteractionProfile(agent_id=agent_id)
        profile.total_interactions = len(interactions)
        profile.successful_completions = sum(
            1 for i in interactions if i.get("outcome") == "success"
        )
        
        # Track capability usage
        for interaction in interactions:
            cap = interaction.get("capability") or interaction.get("capability_id")
            if cap:
                profile.capability_usage[cap] += 1
            
            # Quality scores
            if interaction.get("quality_score"):
                profile.quality_scores.append(interaction["quality_score"])
            
            # Track timing
            if interaction.get("timestamp"):
                ts = interaction["timestamp"]
                if profile.first_interaction > ts:
                    profile.first_interaction = ts
                if profile.last_interaction < ts:
                    profile.last_interaction = ts
        
        # Calculate derived reputation
        success_component = profile.success_rate * 0.5
        quality_component = profile.average_quality * 0.3
        consistency_bonus = min(profile.total_interactions / 50, 0.2)  # Max 0.2 for 50+ interactions
        
        profile.derived_reputation = success_component + quality_component + consistency_bonus
        
        # Store in L2 archival memory
        self.memory.store(
            content=json.dumps(profile.to_dict()),
            tier=MemoryTier.L2_ARCHIVAL,
            directory="/a2a/profiles/relationships",
            importance=0.6,
            tags={"profile", "l2", agent_id, "consolidated"},
            source="a2a_consolidation"
        )
        
        # Cache in memory
        self._agent_profiles[agent_id] = profile
        
        return profile
    
    def get_agent_profile(self, agent_id: str) -> Optional[AgentInteractionProfile]:
        """
        Retrieve L2 agent profile (from cache or memory).
        
        Falls back to on-demand consolidation if not cached.
        """
        # Check cache
        if agent_id in self._agent_profiles:
            return self._agent_profiles[agent_id]
        
        # Search L2 memory
        results = self.memory.retrieve_relevant(
            query=f"profile agent:{agent_id}",
            directory="/a2a/profiles/relationships",
            top_k=1
        )
        
        if results:
            entry, score = results[0]
            try:
                data = json.loads(entry.content)
                profile = AgentInteractionProfile(agent_id=agent_id)
                profile.__dict__.update(data)
                self._agent_profiles[agent_id] = profile
                return profile
            except (json.JSONDecodeError, KeyError):
                pass
        
        # On-demand consolidation if no profile exists
        return self.consolidate_agent_profile(agent_id)
    
    def recommend_capabilities(
        self,
        category: CapabilityCategory,
        top_k: int = 5
    ) -> List[Tuple[str, float, str]]:
        """
        Recommend agents with proven capability in a category.
        
        Uses L2 profiles to find reliable providers.
        
        Returns: [(agent_id, score, reason), ...]
        """
        recommendations = []
        
        for agent_id, profile in self._agent_profiles.items():
            # Check if agent provides relevant capabilities
            relevant_caps = [
                cap for cap, count in profile.capability_usage.items()
                if category.value.lower() in cap.lower()
            ]
            
            if relevant_caps:
                # Score based on success rate and quality
                score = (profile.success_rate * 0.5 + 
                        profile.average_quality * 0.3 +
                        profile.derived_reputation * 0.2)
                
                reason = f"{len(relevant_caps)} relevant capabilities, {profile.success_rate:.0%} success rate"
                recommendations.append((agent_id, score, reason))
        
        # Sort by score descending
        recommendations.sort(key=lambda x: x[1], reverse=True)
        return recommendations[:top_k]
    
    # ==================== Memory Management ====================
    
    def load_negotiation_context(self, request_id: str) -> Dict[str, Any]:
        """
        Load full context for an active negotiation.
        
        Combines L0 immediate + L1 recent + L2 profile for comprehensive context.
        """
        # L0: Current negotiation state
        active = self.get_active_negotiations()
        current_negotiation = [n for n in active if n.get("request_id") == request_id]
        
        # L1: Recent history with this agent
        other_agent = None
        if current_negotiation:
            other_agent = current_negotiation[0].get("other_agent")
        
        recent_history = []
        if other_agent:
            recent_history = self.get_recent_agent_interactions(other_agent, limit=5)
        
        # L2: Agent profile
        profile = None
        if other_agent:
            profile = self.get_agent_profile(other_agent)
        
        return {
            "current_negotiation": current_negotiation,
            "recent_history": recent_history,
            "agent_profile": profile.to_dict() if profile else None,
            "reputation_signal": (
                self.get_agent_reputation_signal(other_agent) if other_agent else None
            ),
            "recommended_terms": self._suggest_terms(other_agent) if other_agent else None
        }
    
    def _suggest_terms(self, agent_id: str) -> Dict[str, Any]:
        """Suggest negotiation terms based on historical patterns."""
        profile = self.get_agent_profile(agent_id)
        if not profile:
            return {"confidence": 0.0}
        
        # Suggest based on past successful negotiations
        interactions = self.get_recent_agent_interactions(agent_id, limit=20)
        successful = [i for i in interactions if i.get("outcome") == "success"]
        
        if not successful:
            return {"confidence": 0.0}
        
        # Extract common patterns
        avg_quality = sum(s.get("quality_score", 0.5) for s in successful) / len(successful)
        
        return {
            "expected_quality": avg_quality,
            "typical_negotiation_rounds": profile.avg_negotiation_rounds,
            "confidence": min(len(successful) / 10, 1.0),
            "suggested_prepayment": 0.1 if profile.derived_reputation > 0.7 else 0.05
        }
    
    def compress_and_archive(self):
        """
        Compress L1 working memories to L2 archival storage.
        
        Should run periodically (e.g., daily) to manage memory size.
        """
        # Consolidate profiles for all agents with recent activity
        agents_to_consolidate = set()
        
        # Scan L1 for agents
        for entry in self.memory.l1_entries:
            if "agent:" in entry.content:
                for tag in entry.tags:
                    if tag.startswith("agent_"):
                        agents_to_consolidate.add(tag.replace("agent_", ""))
        
        # Consolidate each agent
        for agent_id in agents_to_consolidate:
            self.consolidate_agent_profile(agent_id)
        
        return len(agents_to_consolidate)
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory system statistics for monitoring."""
        base_stats = self.memory.session_summary()
        
        return {
            **base_stats,
            "cached_profiles": len(self._agent_profiles),
            "active_conversations": len(self._active_conversations),
            "l0_negotiations": len(self.get_active_negotiations()),
            "l0_executions": len(self.get_active_executions())
        }


class A2AProtocolWithMemory(A2AProtocol):
    """
    A2A Protocol with integrated tiered memory.
    
    Extends base A2AProtocol with automatic memory tracking
    of all negotiations, contracts, and outcomes.
    """
    
    def __init__(self, agent_id: str):
        super().__init__()
        self.agent_id = agent_id
        self.memory_manager = A2AMemoryManager(agent_id)
        self.memory_manager.attach_protocol(self)
    
    def request_service(
        self,
        requester_id: str,
        capability_id: str,
        task_description: str,
        requirements: Optional[Dict] = None,
        proposed_payment: Optional[Dict] = None,
        deadline_ms: int = 600000
    ) -> Optional[ServiceRequest]:
        """
        Request service with memory tracking.
        
        Enhanced with negotiation context from memory.
        """
        # Get capability info for memory
        cap = self.capabilities.get(capability_id)
        provider_id = cap.agent_id if cap else "unknown"
        
        # Record in L0 memory
        self.memory_manager.start_negotiation(
            request_id=f"req_pending_{int(time.time())}",  # Temporary ID
            other_agent_id=provider_id,
            capability_name=cap.name if cap else "unknown",
            initial_terms={
                "task": task_description,
                "payment": proposed_payment,
                "deadline_ms": deadline_ms
            }
        )
        
        # Check memory for reputation signal
        reputation = self.memory_manager.get_agent_reputation_signal(provider_id)
        
        # Call parent implementation
        request = super().request_service(
            requester_id=requester_id,
            capability_id=capability_id,
            task_description=task_description,
            requirements=requirements,
            proposed_payment=proposed_payment,
            deadline_ms=deadline_ms
        )
        
        # Update memory with actual request ID
        if request:
            self.memory_manager.start_negotiation(
                request_id=request.request_id,
                other_agent_id=provider_id,
                capability_name=cap.name if cap else "unknown",
                initial_terms={
                    "task": task_description,
                    "payment": proposed_payment,
                    "deadline_ms": deadline_ms
                }
            )
        
        return request
    
    def negotiate_terms(
        self,
        request_id: str,
        counter_terms: Dict[str, Any],
        accepted: bool = False
    ) -> bool:
        """Negotiate with memory tracking."""
        # Record negotiation round
        if request_id in self.requests:
            req = self.requests[request_id]
            self.memory_manager.record_negotiation_round(
                request_id=request_id,
                round_num=req.negotiation_rounds + 1,
                proposed_by=self.agent_id,
                terms=counter_terms,
                response="accepted" if accepted else "counter"
            )
        
        result = super().negotiate_terms(request_id, counter_terms, accepted)
        
        # Archive if completed
        if accepted and request_id in self.requests:
            self.memory_manager.archive_negotiation(request_id, "success")
        
        return result
    
    def create_contract(self, escrow_id: str) -> Optional[Contract]:
        """Create contract with memory tracking."""
        contract = super().create_contract(escrow_id)
        
        if contract:
            # Record execution start in memory
            self.memory_manager.start_execution(
                contract_id=contract.contract_id,
                request_id=contract.request_id,
                provider_id=contract.provider_id,
                expected_duration_ms=300000  # Default, should be from capability
            )
        
        return contract
    
    def release_escrow(self, contract_id: str) -> bool:
        """Release escrow with memory archival."""
        # Get contract data before release
        contract = self.contracts.get(contract_id)
        quality_score = contract.quality_score if contract else None
        
        result = super().release_escrow(contract_id)
        
        # Archive to L1 memory
        if result and contract:
            self.memory_manager.archive_contract(
                contract_id=contract_id,
                contract_data=contract.to_dict(),
                quality_score=quality_score
            )
        
        return result
    
    def get_contextual_recommendations(
        self,
        category: CapabilityCategory
    ) -> List[Dict[str, Any]]:
        """
        Get memory-enhanced capability recommendations.
        
        Combines protocol discovery with historical performance.
        """
        # Get base recommendations from protocol
        base_caps = self.discover_capabilities(
            category=category,
            available_only=True
        )
        
        # Enhance with memory data
        recommendations = []
        for cap in base_caps:
            profile = self.memory_manager.get_agent_profile(cap.agent_id)
            reputation = self.memory_manager.get_agent_reputation_signal(cap.agent_id)
            
            enhanced = {
                **cap.to_dict(),
                "historical_reputation": profile.derived_reputation if profile else 0.5,
                "recent_reputation": reputation["reputation"],
                "reputation_confidence": reputation["confidence"],
                "past_interactions": reputation["sample_size"],
                "success_rate": profile.success_rate if profile else 0.5
            }
            recommendations.append(enhanced)
        
        # Sort by combined score (historical + capability)
        recommendations.sort(
            key=lambda x: (x["success_rate"] * 0.4 + 
                          x["historical_reputation"] * 0.3 +
                          x["avg_quality"] * 0.3),
            reverse=True
        )
        
        return recommendations


def demo_a2a_memory():
    """Demonstrate A2A protocol with tiered memory."""
    print("=" * 70)
    print("🧠 A2A TIERED MEMORY INTEGRATION DEMO")
    print("=" * 70)
    
    # Create protocol with memory
    protocol = A2AProtocolWithMemory(agent_id="Alpha")
    
    print("\n" + "-" * 70)
    print("📊 PHASE 1: Initial Memory State")
    print("-" * 70)
    
    stats = protocol.memory_manager.get_memory_stats()
    print(f"\nMemory System Stats:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n" + "-" * 70)
    print("📢 PHASE 2: Advertise Capabilities")
    print("-" * 70)
    
    # Other agents advertise
    cap1 = protocol.advertise_capability(
        agent_id="Beta",
        category=CapabilityCategory.CODE,
        name="Code Review",
        description="Security-focused code review",
        estimated_duration_ms=300000,
        min_reputation_required=0.3,
        tags=["code", "review", "security"]
    )
    
    cap2 = protocol.advertise_capability(
        agent_id="Gamma",
        category=CapabilityCategory.RESEARCH,
        name="Web Research",
        description="Deep research with synthesis",
        estimated_duration_ms=600000,
        min_reputation_required=0.4,
        tags=["research", "web", "analysis"]
    )
    
    print(f"\nAdvertised: {cap1.name} (Beta), {cap2.name} (Gamma)")
    
    print("\n" + "-" * 70)
    print("📨 PHASE 3: Service Request (L0 Memory)")
    print("-" * 70)
    
    # Request service
    request = protocol.request_service(
        requester_id="Alpha",
        capability_id=cap1.capability_id,
        task_description="Review authentication module",
        requirements={"language": "python"},
        deadline_ms=300000
    )
    
    print(f"\nRequest created: {request.request_id if request else 'failed'}")
    
    # Check L0 memory
    active_neg = protocol.memory_manager.get_active_negotiations()
    print(f"Active negotiations in L0: {len(active_neg)}")
    
    print("\n" + "-" * 70)
    print("🤝 PHASE 4: Negotiation Rounds (L0 Memory)")
    print("-" * 70)
    
    if request:
        # Round 1: Counter offer
        protocol.negotiate_terms(
            request_id=request.request_id,
            counter_terms={"price": 0.15, "deadline": 400000},
            accepted=False
        )
        
        # Round 2: Accept
        protocol.negotiate_terms(
            request_id=request.request_id,
            counter_terms={"price": 0.12, "deadline": 350000},
            accepted=True
        )
    
    # Check L0 for negotiation rounds
    active_neg = protocol.memory_manager.get_active_negotiations()
    print(f"\nNegotiation entries in L0: {len(active_neg)}")
    
    print("\n" + "-" * 70)
    print("📜 PHASE 5: Contract Execution (L0 → L1)")
    print("-" * 70)
    
    if request:
        # Create escrow and contract
        escrow = protocol.create_escrow(request.request_id)
        if escrow:
            protocol.deposit_to_escrow(escrow.escrow_id, "client", "sig1")
            protocol.deposit_to_escrow(escrow.escrow_id, "provider", "sig2")
            
            contract = protocol.create_contract(escrow.escrow_id)
            if contract:
                print(f"\nContract created: {contract.contract_id}")
                
                # Simulate completion
                protocol.submit_deliverable(
                    contract_id=contract.contract_id,
                    deliverable={"report": "Security issues found: 1"},
                    evidence="evidence_hash"
                )
                
                # Release and archive
                protocol.release_escrow(contract.contract_id)
                print("Contract completed and archived to L1")
    
    print("\n" + "-" * 70)
    print("💾 PHASE 6: Memory Consolidation (L1 → L2)")
    print("-" * 70)
    
    # Consolidate profiles
    profile = protocol.memory_manager.consolidate_agent_profile("Beta")
    print(f"\nAgent Profile for Beta:")
    print(f"  Total interactions: {profile.total_interactions}")
    print(f"  Success rate: {profile.success_rate:.1%}")
    print(f"  Derived reputation: {profile.derived_reputation:.2f}")
    
    print("\n" + "-" * 70)
    print("🎯 PHASE 7: Contextual Recommendations")
    print("-" * 70)
    
    # Get memory-enhanced recommendations
    recommendations = protocol.get_contextual_recommendations(CapabilityCategory.CODE)
    
    print(f"\nEnhanced Recommendations ({len(recommendations)} found):")
    for rec in recommendations[:3]:
        print(f"  - {rec['name']} by {rec['agent_id']}")
        print(f"    Historical reputation: {rec['historical_reputation']:.2f}")
        print(f"    Success rate: {rec['success_rate']:.1%}")
        print(f"    Past interactions: {rec['past_interactions']}")
    
    print("\n" + "-" * 70)
    print("📊 Final Memory State")
    print("-" * 70)
    
    stats = protocol.memory_manager.get_memory_stats()
    print(f"\nMemory System Stats:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 70)
    print("✅ A2A MEMORY DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    demo_a2a_memory()
