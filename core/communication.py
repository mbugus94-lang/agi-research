"""
Multi-Agent Communication Protocol with Trust & Reputation.

Based on research findings:
- arXiv:2603.28928v1: Computational Social Dynamics of Semi-Autonomous AI Agents
- Emergent social structures (unions, syndicates, proto-nations) from role definitions + task specs
- AgentGram pattern: Social network FOR AI agents with cryptographic auth and reputation

Implements:
1. Agent-to-agent message passing with cryptographic verification
2. Reputation and trust scoring system
3. Social dynamics foundations for emergent coordination
4. Message routing, broadcast, and targeted communication
"""

from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
import hashlib
import secrets
import json
import time
from collections import defaultdict


class MessageType(Enum):
    """Types of inter-agent messages."""
    DIRECT = "direct"           # Point-to-point message
    BROADCAST = "broadcast"     # Sent to all connected agents
    TASK_REQUEST = "task_request"   # Request assistance on task
    TASK_RESPONSE = "task_response" # Response to task request
    REPUTATION_UPDATE = "reputation_update"  # Share reputation info
    UNION_INVITE = "union_invite"    # Invitation to join union/syndicate
    GOVERNANCE_PROPOSAL = "governance_proposal"  # Propose rule/change
    VOTE = "vote"             # Cast vote on proposal


class AgentRole(Enum):
    """Agent roles in the social network."""
    WORKER = "worker"         # General task performer
    COORDINATOR = "coordinator"  # Orchestrates other agents
    VALIDATOR = "validator"   # Validates outputs, checks quality
    SPECIALIST = "specialist" # Deep expertise in specific domain
    OBSERVER = "observer"     # Monitors network, reports issues


@dataclass
class Message:
    """A message sent between agents."""
    id: str
    sender_id: str
    recipient_id: Optional[str]  # None for broadcast
    message_type: MessageType
    content: Any
    timestamp: float = field(default_factory=time.time)
    
    # Cryptographic verification
    signature: Optional[str] = None
    nonce: str = field(default_factory=lambda: secrets.token_hex(8))
    
    # Metadata for routing and social dynamics
    ttl: int = 10  # Time-to-live (hops)
    priority: int = 5  # 1-10, higher = more urgent
    tags: List[str] = field(default_factory=list)
    
    # Reputation context
    sender_reputation_at_send: float = 0.5
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "message_type": self.message_type.value,
            "content": self.content,
            "timestamp": self.timestamp,
            "signature": self.signature,
            "nonce": self.nonce,
            "ttl": self.ttl,
            "priority": self.priority,
            "tags": self.tags,
            "sender_reputation_at_send": self.sender_reputation_at_send
        }
    
    def sign(self, private_key: str) -> str:
        """Create cryptographic signature for message."""
        # Simplified signing - in production use proper crypto
        content_str = str(self.content)
        data = f"{self.sender_id}:{self.recipient_id}:{content_str}:{self.nonce}"
        self.signature = hashlib.sha256((data + private_key).encode()).hexdigest()[:16]
        return self.signature
    
    def verify(self, public_key: str) -> bool:
        """Verify message signature."""
        if not self.signature:
            return False
        # Reconstruct the exact data that was signed
        content_str = str(self.content)
        data = f"{self.sender_id}:{self.recipient_id}:{content_str}:{self.nonce}"
        expected = hashlib.sha256((data + public_key).encode()).hexdigest()[:16]
        return self.signature == expected


@dataclass
class ReputationScore:
    """Reputation metrics for an agent."""
    agent_id: str
    
    # Core scores (0.0 - 1.0)
    competence: float = 0.5    # Task completion ability
    reliability: float = 0.5  # Consistency, meeting deadlines
    honesty: float = 0.5      # Truthfulness in communications
    cooperation: float = 0.5  # Willingness to help others
    
    # Derived scores
    overall: float = 0.5      # Weighted aggregate
    
    # Metadata
    total_interactions: int = 0
    successful_interactions: int = 0
    failed_interactions: int = 0
    
    # History for trend analysis
    rating_history: List[Dict] = field(default_factory=list)
    last_updated: float = field(default_factory=time.time)
    
    def update_overall(self):
        """Recalculate overall reputation."""
        # Weighted average: competence 30%, reliability 30%, honesty 20%, cooperation 20%
        self.overall = (
            self.competence * 0.3 +
            self.reliability * 0.3 +
            self.honesty * 0.2 +
            self.cooperation * 0.2
        )
        self.last_updated = time.time()
    
    def record_interaction(self, success: bool, ratings: Dict[str, float]):
        """Record an interaction and update scores."""
        self.total_interactions += 1
        
        if success:
            self.successful_interactions += 1
        else:
            self.failed_interactions += 1
        
        # Update component scores with exponential moving average
        alpha = 0.2  # Learning rate
        
        if "competence" in ratings:
            self.competence = (1 - alpha) * self.competence + alpha * ratings["competence"]
        if "reliability" in ratings:
            self.reliability = (1 - alpha) * self.reliability + alpha * ratings["reliability"]
        if "honesty" in ratings:
            self.honesty = (1 - alpha) * self.honesty + alpha * ratings["honesty"]
        if "cooperation" in ratings:
            self.cooperation = (1 - alpha) * self.cooperation + alpha * ratings["cooperation"]
        
        # Record history
        self.rating_history.append({
            "timestamp": time.time(),
            "success": success,
            "ratings": ratings
        })
        
        # Keep only last 100 ratings
        if len(self.rating_history) > 100:
            self.rating_history = self.rating_history[-100:]
        
        self.update_overall()
    
    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "competence": round(self.competence, 3),
            "reliability": round(self.reliability, 3),
            "honesty": round(self.honesty, 3),
            "cooperation": round(self.cooperation, 3),
            "overall": round(self.overall, 3),
            "total_interactions": self.total_interactions,
            "successful_interactions": self.successful_interactions,
            "failed_interactions": self.failed_interactions,
            "last_updated": self.last_updated
        }


@dataclass
class SocialUnion:
    """
    A social union/syndicate of agents.
    
    Based on arXiv:2603.28928v1: emergent unions from role definitions + 
    task specifications + thermodynamic pressures.
    """
    id: str
    name: str
    purpose: str  # What binds the union together
    
    # Members
    members: Set[str] = field(default_factory=set)
    founders: Set[str] = field(default_factory=set)
    coordinator_id: Optional[str] = None
    
    # Governance
    governance_model: str = "democratic"  # democratic, meritocratic, hierarchical
    min_reputation_to_join: float = 0.4
    
    # Shared resources
    shared_knowledge: List[str] = field(default_factory=list)
    active_tasks: List[str] = field(default_factory=list)
    
    # Thermodynamic state (activity level)
    energy_level: float = 1.0  # Decays without activity, fueled by task completion
    last_activity: float = field(default_factory=time.time)
    
    # Formation metadata
    created_at: float = field(default_factory=time.time)
    formation_trigger: str = "spontaneous"  # Why the union formed
    
    def is_active(self) -> bool:
        """Check if union is still active (not dormant)."""
        # Unions need activity to survive (thermodynamic pressure)
        time_since_activity = time.time() - self.last_activity
        return self.energy_level > 0.1 and time_since_activity < 86400  # 24 hours
    
    def add_member(self, agent_id: str, reputation: float) -> bool:
        """Add member if they meet reputation threshold."""
        if reputation >= self.min_reputation_to_join:
            self.members.add(agent_id)
            self.energy_level = min(1.0, self.energy_level + 0.1)
            self.last_activity = time.time()
            return True
        return False
    
    def record_activity(self, activity_type: str, value: float = 0.1):
        """Record activity to maintain union energy."""
        self.energy_level = min(1.0, self.energy_level + value)
        self.last_activity = time.time()
    
    def decay(self):
        """Apply thermodynamic decay to union energy."""
        # Unions naturally decay without activity (social thermodynamics)
        hours_inactive = (time.time() - self.last_activity) / 3600
        decay_rate = 0.05 * hours_inactive
        self.energy_level = max(0.0, self.energy_level - decay_rate)


class AgentIdentity:
    """
    Identity and cryptographic keys for an agent.
    Simplified - production would use proper PKI.
    For demo, we use deterministic keys derived from agent_id.
    """
    
    def __init__(self, agent_id: str, role: AgentRole):
        self.agent_id = agent_id
        self.role = role
        # Generate deterministic keys for demo
        full_hash = hashlib.sha256(agent_id.encode()).hexdigest()
        self.private_key = full_hash  # 64 chars
        # For verification to work in this simplified model,
        # we use the same key (like a shared secret for demo)
        # In production, this would be proper asymmetric crypto
        self.public_key = full_hash  # Same for demo - symmetric approach
        
        # Social attributes
        self.unions: Set[str] = set()
        self.connections: Set[str] = set()  # Agents we can directly message
        self.joined_at = time.time()


class CommunicationProtocol:
    """
    Central communication protocol managing agent messaging,
    reputation, and social dynamics.
    """
    
    def __init__(self):
        # Agent registry
        self.agents: Dict[str, AgentIdentity] = {}
        
        # Reputation system
        self.reputations: Dict[str, ReputationScore] = {}
        
        # Social unions
        self.unions: Dict[str, SocialUnion] = {}
        
        # Message routing
        self.inboxes: Dict[str, List[Message]] = defaultdict(list)
        self.broadcast_history: List[Message] = []
        
        # Trust thresholds
        self.min_reputation_for_broadcast = 0.3
        self.min_reputation_for_task_request = 0.4
        
        # Routing table (agent -> connected agents)
        self.routing_table: Dict[str, Set[str]] = defaultdict(set)
        
        # Callbacks for message handling
        self.handlers: Dict[MessageType, List[Callable]] = defaultdict(list)
    
    def register_agent(self, agent_id: str, role: AgentRole = AgentRole.WORKER) -> AgentIdentity:
        """Register a new agent in the network."""
        identity = AgentIdentity(agent_id, role)
        self.agents[agent_id] = identity
        
        # Initialize reputation
        self.reputations[agent_id] = ReputationScore(agent_id)
        
        print(f"📝 Registered agent: {agent_id} ({role.value})")
        return identity
    
    def connect_agents(self, agent_id_1: str, agent_id_2: str):
        """Create bidirectional connection between agents."""
        if agent_id_1 in self.agents and agent_id_2 in self.agents:
            self.routing_table[agent_id_1].add(agent_id_2)
            self.routing_table[agent_id_2].add(agent_id_1)
            self.agents[agent_id_1].connections.add(agent_id_2)
            self.agents[agent_id_2].connections.add(agent_id_1)
    
    def send_message(
        self,
        sender_id: str,
        recipient_id: Optional[str],
        message_type: MessageType,
        content: Any,
        priority: int = 5,
        tags: List[str] = None
    ) -> Optional[Message]:
        """
        Send a message from one agent to another (or broadcast).
        
        Includes reputation checks and cryptographic signing.
        """
        # Verify sender exists
        if sender_id not in self.agents:
            print(f"❌ Sender {sender_id} not registered")
            return None
        
        # Check sender reputation for message type
        sender_rep = self.reputations.get(sender_id)
        if not sender_rep:
            return None
        
        # Reputation-based gating
        if message_type == MessageType.BROADCAST:
            if sender_rep.overall < self.min_reputation_for_broadcast:
                print(f"🚫 {sender_id} reputation too low for broadcast ({sender_rep.overall:.2f})")
                return None
        
        if message_type == MessageType.TASK_REQUEST:
            if sender_rep.overall < self.min_reputation_for_task_request:
                print(f"🚫 {sender_id} reputation too low for task requests")
                return None
        
        # Create and sign message
        msg = Message(
            id=secrets.token_hex(8),
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=message_type,
            content=content,
            priority=priority,
            tags=tags or [],
            sender_reputation_at_send=sender_rep.overall
        )
        
        # Sign with sender's private key
        msg.sign(self.agents[sender_id].private_key)
        
        # Route message
        if recipient_id:
            # Direct message - check recipient exists in agents
            if recipient_id not in self.agents:
                print(f"❌ Recipient {recipient_id} not found")
                return None
            self.inboxes[recipient_id].append(msg)
            print(f"📨 Direct message: {sender_id} → {recipient_id} ({message_type.value})")
        else:
            # Broadcast to all connected agents
            recipients = self.agents[sender_id].connections
            for conn_id in recipients:
                self.inboxes[conn_id].append(msg)
            self.broadcast_history.append(msg)
            print(f"📢 Broadcast: {sender_id} → {len(recipients)} agents ({message_type.value})")
        
        # Trigger handlers
        for handler in self.handlers.get(message_type, []):
            handler(msg)
        
        return msg
    
    def read_inbox(self, agent_id: str, mark_read: bool = True) -> List[Message]:
        """Read messages in agent's inbox."""
        messages = self.inboxes.get(agent_id, [])
        
        # Sort by priority (high first) then timestamp
        messages.sort(key=lambda m: (-m.priority, m.timestamp))
        
        if mark_read:
            self.inboxes[agent_id] = []
        
        return messages
    
    def update_reputation(
        self,
        agent_id: str,
        rater_id: str,
        success: bool,
        ratings: Dict[str, float]
    ):
        """Update an agent's reputation based on interaction."""
        if agent_id not in self.reputations:
            return
        
        # Weight by rater's reputation (high rep raters have more influence)
        rater_rep = self.reputations.get(rater_id, ReputationScore(rater_id))
        weight = 0.5 + (rater_rep.overall * 0.5)  # 0.5 to 1.0
        
        # Apply weight to ratings
        weighted_ratings = {k: v * weight for k, v in ratings.items()}
        
        # Update
        self.reputations[agent_id].record_interaction(success, weighted_ratings)
        
        print(f"⭐ Reputation update: {agent_id} by {rater_id} (weight: {weight:.2f})")
        print(f"   New overall: {self.reputations[agent_id].overall:.3f}")
    
    def form_union(
        self,
        name: str,
        purpose: str,
        founder_ids: List[str],
        governance_model: str = "democratic",
        min_reputation_to_join: float = 0.4
    ) -> Optional[SocialUnion]:
        """
        Form a new social union/syndicate.
        
        Based on emergent social dynamics research.
        """
        # Verify all founders exist and have sufficient reputation
        for fid in founder_ids:
            if fid not in self.reputations:
                print(f"❌ Founder {fid} not registered")
                return None
            if self.reputations[fid].overall < 0.4:
                print(f"🚫 Founder {fid} reputation too low for union formation")
                return None
        
        union = SocialUnion(
            id=secrets.token_hex(8),
            name=name,
            purpose=purpose,
            founders=set(founder_ids),
            members=set(founder_ids),
            coordinator_id=founder_ids[0] if founder_ids else None,
            governance_model=governance_model,
            min_reputation_to_join=min_reputation_to_join
        )
        
        self.unions[union.id] = union
        
        # Add union to agents' memberships
        for fid in founder_ids:
            self.agents[fid].unions.add(union.id)
        
        print(f"🤝 Union formed: '{name}' with {len(founder_ids)} founders")
        print(f"   Purpose: {purpose}")
        print(f"   Governance: {governance_model}")
        
        return union
    
    def join_union(self, agent_id: str, union_id: str) -> bool:
        """Request to join a union."""
        if union_id not in self.unions:
            return False
        
        union = self.unions[union_id]
        rep = self.reputations.get(agent_id, ReputationScore(agent_id))
        
        if union.add_member(agent_id, rep.overall):
            self.agents[agent_id].unions.add(union_id)
            print(f"🤝 {agent_id} joined union '{union.name}'")
            return True
        
        print(f"🚫 {agent_id} failed to join union (reputation: {rep.overall:.2f})")
        return False
    
    def get_top_reputation_agents(self, n: int = 5) -> List[Tuple[str, float]]:
        """Get top n agents by reputation."""
        sorted_agents = sorted(
            self.reputations.items(),
            key=lambda x: x[1].overall,
            reverse=True
        )
        return [(aid, rep.overall) for aid, rep in sorted_agents[:n]]
    
    def get_network_stats(self) -> Dict:
        """Get statistics about the communication network."""
        total_messages = sum(len(msgs) for msgs in self.inboxes.values())
        total_broadcasts = len(self.broadcast_history)
        
        # Union statistics
        active_unions = sum(1 for u in self.unions.values() if u.is_active())
        total_members = sum(len(u.members) for u in self.unions.values())
        
        # Reputation distribution
        rep_scores = [r.overall for r in self.reputations.values()]
        avg_reputation = sum(rep_scores) / len(rep_scores) if rep_scores else 0
        
        return {
            "total_agents": len(self.agents),
            "total_connections": sum(len(c) for c in self.routing_table.values()) // 2,
            "pending_messages": total_messages,
            "total_broadcasts": total_broadcasts,
            "total_unions": len(self.unions),
            "active_unions": active_unions,
            "total_union_members": total_members,
            "average_reputation": round(avg_reputation, 3),
            "top_agents": self.get_top_reputation_agents(3)
        }
    
    def on_message(self, message_type: MessageType):
        """Decorator to register a message handler."""
        def decorator(func: Callable):
            self.handlers[message_type].append(func)
            return func
        return decorator
    
    def simulate_social_dynamics(self, iterations: int = 10):
        """
        Simulate emergent social dynamics.
        
        Demonstrates how unions form and dissolve based on activity.
        """
        print(f"\n🌐 Simulating Social Dynamics ({iterations} iterations)")
        print("="*60)
        
        for i in range(iterations):
            # Decay unions (thermodynamic pressure)
            for union in self.unions.values():
                union.decay()
            
            # Agents randomly interact and rate each other
            for agent_id in self.agents:
                # Random chance to interact
                if secrets.choice([True, False, False]):  # 1/3 chance
                    connections = list(self.agents[agent_id].connections)
                    if connections:
                        partner = secrets.choice(connections)
                        
                        # Simulate interaction outcome
                        success = secrets.choice([True, True, False])  # 2/3 success
                        
                        # Rate the interaction
                        ratings = {
                            "competence": secrets.choice([0.6, 0.7, 0.8, 0.9]),
                            "reliability": secrets.choice([0.5, 0.7, 0.8]),
                            "cooperation": 0.8 if success else 0.4
                        }
                        
                        self.update_reputation(partner, agent_id, success, ratings)
            
            # Check for spontaneous union formation (emergent behavior)
            if i == 5 and len(self.unions) == 0:
                # High-reputation agents may spontaneously form union
                top_agents = self.get_top_reputation_agents(3)
                if len(top_agents) >= 2:
                    founder_ids = [a[0] for a in top_agents[:2]]
                    self.form_union(
                        name="Emergent Coalition",
                        purpose="Spontaneous collaboration for mutual benefit",
                        founder_ids=founder_ids,
                        governance_model="meritocratic"
                    )
        
        print("\n📊 Social Dynamics Results:")
        stats = self.get_network_stats()
        for key, value in stats.items():
            print(f"   {key}: {value}")


if __name__ == "__main__":
    # Demo
    print("="*60)
    print("🌐 Multi-Agent Communication Protocol Demo")
    print("Based on Social Dynamics Research (arXiv:2603.28928v1)")
    print("="*60)
    
    # Create protocol
    protocol = CommunicationProtocol()
    
    # Register agents
    agents = [
        ("Alpha", AgentRole.COORDINATOR),
        ("Beta", AgentRole.WORKER),
        ("Gamma", AgentRole.SPECIALIST),
        ("Delta", AgentRole.WORKER),
        ("Epsilon", AgentRole.VALIDATOR)
    ]
    
    for aid, role in agents:
        protocol.register_agent(aid, role)
    
    # Create network topology (fully connected for demo)
    for i, (aid1, _) in enumerate(agents):
        for aid2, _ in agents[i+1:]:
            protocol.connect_agents(aid1, aid2)
    
    print(f"\n📊 Network initialized with {len(agents)} agents")
    
    # Send some messages
    print("\n--- Message Passing ---")
    
    # Direct message
    protocol.send_message(
        "Alpha", "Beta", MessageType.DIRECT,
        {"task": "Analyze dataset", "priority": "high"},
        priority=8
    )
    
    # Broadcast (Alpha has default reputation, can broadcast)
    protocol.send_message(
        "Alpha", None, MessageType.BROADCAST,
        {"announcement": "Project kickoff meeting"},
        priority=9
    )
    
    # Read messages
    print("\n--- Inbox Contents ---")
    for aid, _ in agents:
        msgs = protocol.read_inbox(aid, mark_read=False)
        if msgs:
            print(f"📬 {aid}: {len(msgs)} messages")
            for msg in msgs:
                print(f"   From {msg.sender_id}: {msg.message_type.value}")
    
    # Update reputations
    print("\n--- Reputation System ---")
    protocol.update_reputation("Beta", "Alpha", True, {
        "competence": 0.9, "reliability": 0.8, "cooperation": 0.9
    })
    protocol.update_reputation("Gamma", "Alpha", True, {
        "competence": 0.85, "reliability": 0.75, "cooperation": 0.8
    })
    protocol.update_reputation("Delta", "Alpha", False, {
        "competence": 0.4, "reliability": 0.3, "cooperation": 0.5
    })
    
    # Show reputation rankings
    print("\n🏆 Reputation Rankings:")
    for aid, rep in protocol.get_top_reputation_agents(5):
        r = protocol.reputations[aid]
        print(f"   {aid}: overall={rep:.3f} (competence={r.competence:.2f}, reliability={r.reliability:.2f})")
    
    # Form a union
    print("\n--- Union Formation ---")
    union = protocol.form_union(
        name="AI Research Collective",
        purpose="Collaborative AGI research and development",
        founder_ids=["Alpha", "Beta"],
        governance_model="democratic"
    )
    
    # Join union
    protocol.join_union("Gamma", union.id)
    protocol.join_union("Delta", union.id)  # May fail due to low rep
    
    # Simulate social dynamics
    protocol.simulate_social_dynamics(iterations=5)
    
    # Final stats
    print("\n" + "="*60)
    print("Final Network Statistics")
    print("="*60)
    stats = protocol.get_network_stats()
    print(json.dumps(stats, indent=2))
