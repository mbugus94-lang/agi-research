"""
A2A (Agent-to-Agent) Protocol Implementation

Based on Google's emerging Agent Runtime standard and A2A protocol research.
Enables secure, structured communication between autonomous agents with:
- Message passing with structured envelopes
- Agent discovery and registry
- Handoff and delegation mechanisms
- Memory sharing with escrow patterns
- Capability negotiation
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Set
from enum import Enum, auto
from datetime import datetime
import json
import uuid
import hashlib
from collections import defaultdict


class MessageType(Enum):
    """A2A message types for agent communication."""
    REQUEST = auto()      # Request for action/information
    RESPONSE = auto()     # Response to a request
    DELEGATE = auto()     # Delegate task to another agent
    HANDOFF = auto()      # Transfer conversation/context
    NOTIFY = auto()       # One-way notification
    HEARTBEAT = auto()    # Health check
    DISCOVER = auto()     # Capability discovery
    ESCROW = auto()       # Memory/data escrow operation


class EscrowAction(Enum):
    """Actions for escrow operations."""
    LOCK = auto()         # Lock memory for shared access
    RELEASE = auto()      # Release locked memory
    COMMIT = auto()       # Commit shared changes
    ROLLBACK = auto()     # Rollback to previous state


class HandoffMode(Enum):
    """Modes for agent handoff."""
    FULL = auto()         # Full context transfer
    PARTIAL = auto()      # Partial context (filtered)
    TEMPORARY = auto()    # Temporary delegation (returns)
    PERMANENT = auto()    # Permanent transfer


@dataclass
class AgentCapability:
    """Describes an agent's capabilities for discovery."""
    name: str
    description: str
    version: str = "1.0"
    parameters: Dict[str, Any] = field(default_factory=dict)
    requirements: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "parameters": self.parameters,
            "requirements": self.requirements
        }


@dataclass  
class A2AEnvelope:
    """Standard envelope for A2A messages."""
    message_id: str
    message_type: MessageType
    sender_id: str
    recipient_id: str
    timestamp: datetime
    correlation_id: Optional[str] = None  # Links requests to responses
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    signature: Optional[str] = None  # For message integrity
    ttl: int = 300  # Time-to-live in seconds
    
    def __post_init__(self):
        if isinstance(self.message_type, str):
            self.message_type = MessageType[self.message_type.upper()]
        if isinstance(self.timestamp, str):
            self.timestamp = datetime.fromisoformat(self.timestamp)
    
    def to_dict(self) -> Dict:
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.name,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "payload": self.payload,
            "metadata": self.metadata,
            "signature": self.signature,
            "ttl": self.ttl
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'A2AEnvelope':
        return cls(
            message_id=data["message_id"],
            message_type=MessageType[data["message_type"]],
            sender_id=data["sender_id"],
            recipient_id=data["recipient_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            correlation_id=data.get("correlation_id"),
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
            signature=data.get("signature"),
            ttl=data.get("ttl", 300)
        )
    
    def sign(self, secret: str) -> 'A2AEnvelope':
        """Sign the message for integrity verification."""
        content = f"{self.message_id}:{self.sender_id}:{self.recipient_id}:{json.dumps(self.payload, sort_keys=True)}"
        self.signature = hashlib.sha256(f"{content}:{secret}".encode()).hexdigest()
        return self
    
    def verify(self, secret: str) -> bool:
        """Verify message signature."""
        if not self.signature:
            return False
        content = f"{self.message_id}:{self.sender_id}:{self.recipient_id}:{json.dumps(self.payload, sort_keys=True)}"
        expected = hashlib.sha256(f"{content}:{secret}".encode()).hexdigest()
        return self.signature == expected


@dataclass
class AgentIdentity:
    """Identity and metadata for an agent in the A2A network."""
    agent_id: str
    name: str
    capabilities: List[AgentCapability] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "active"  # active, busy, offline
    last_seen: Optional[datetime] = None
    
    def __post_init__(self):
        if not self.agent_id:
            self.agent_id = str(uuid.uuid4())
        if not self.last_seen:
            self.last_seen = datetime.now()


class A2AMemoryEscrow:
    """
    Memory escrow system for secure shared access between agents.
    Implements lock-release-commit-rollback pattern for collaborative memory.
    """
    
    def __init__(self):
        self._escrows: Dict[str, Dict] = {}  # escrow_id -> escrow data
        self._locks: Dict[str, Set[str]] = defaultdict(set)  # memory_key -> agent_ids
        self._history: List[Dict] = []
    
    def create_escrow(self, memory_key: str, owner_id: str, 
                      data: Any, authorized_agents: List[str]) -> str:
        """Create a new escrow for shared memory access."""
        escrow_id = str(uuid.uuid4())
        self._escrows[escrow_id] = {
            "id": escrow_id,
            "memory_key": memory_key,
            "owner_id": owner_id,
            "data": data,
            "authorized_agents": set(authorized_agents),
            "locked_by": None,
            "locked_at": None,
            "version": 0,
            "history": [data]
        }
        return escrow_id
    
    def lock(self, escrow_id: str, agent_id: str) -> bool:
        """Lock escrow for exclusive access."""
        if escrow_id not in self._escrows:
            return False
        
        escrow = self._escrows[escrow_id]
        if agent_id not in escrow["authorized_agents"]:
            return False
        
        if escrow["locked_by"] is not None:
            return False  # Already locked
        
        escrow["locked_by"] = agent_id
        escrow["locked_at"] = datetime.now()
        self._locks[escrow["memory_key"]].add(agent_id)
        
        self._history.append({
            "action": "lock",
            "escrow_id": escrow_id,
            "agent_id": agent_id,
            "timestamp": datetime.now()
        })
        return True
    
    def read(self, escrow_id: str, agent_id: str) -> Optional[Any]:
        """Read from escrow (no lock required)."""
        if escrow_id not in self._escrows:
            return None
        
        escrow = self._escrows[escrow_id]
        if agent_id not in escrow["authorized_agents"]:
            return None
        
        return escrow["data"]
    
    def write(self, escrow_id: str, agent_id: str, data: Any) -> bool:
        """Write to escrow (requires lock)."""
        if escrow_id not in self._escrows:
            return False
        
        escrow = self._escrows[escrow_id]
        if escrow["locked_by"] != agent_id:
            return False  # Must hold lock
        
        escrow["data"] = data
        escrow["version"] += 1
        
        self._history.append({
            "action": "write",
            "escrow_id": escrow_id,
            "agent_id": agent_id,
            "timestamp": datetime.now(),
            "version": escrow["version"]
        })
        return True
    
    def commit(self, escrow_id: str, agent_id: str) -> bool:
        """Commit changes and release lock."""
        if escrow_id not in self._escrows:
            return False
        
        escrow = self._escrows[escrow_id]
        if escrow["locked_by"] != agent_id:
            return False
        
        # Save to history
        escrow["history"].append(escrow["data"])
        
        # Release lock
        escrow["locked_by"] = None
        escrow["locked_at"] = None
        self._locks[escrow["memory_key"]].discard(agent_id)
        
        self._history.append({
            "action": "commit",
            "escrow_id": escrow_id,
            "agent_id": agent_id,
            "timestamp": datetime.now()
        })
        return True
    
    def rollback(self, escrow_id: str, agent_id: str, 
                 version: Optional[int] = None) -> bool:
        """Rollback to previous version."""
        if escrow_id not in self._escrows:
            return False
        
        escrow = self._escrows[escrow_id]
        if escrow["locked_by"] != agent_id:
            return False
        
        if version is not None and version >= 0 and version < len(escrow["history"]):
            # Rollback to specific version by index
            escrow["data"] = escrow["history"][version]
            escrow["version"] = version
        else:
            # Rollback to most recent committed version (last in history)
            if len(escrow["history"]) > 0:
                escrow["data"] = escrow["history"][-1]
                escrow["version"] = len(escrow["history"]) - 1
        
        self._history.append({
            "action": "rollback",
            "escrow_id": escrow_id,
            "agent_id": agent_id,
            "timestamp": datetime.now()
        })
        return True
    
    def get_status(self, escrow_id: str) -> Optional[Dict]:
        """Get escrow status."""
        if escrow_id not in self._escrows:
            return None
        
        escrow = self._escrows[escrow_id]
        return {
            "id": escrow["id"],
            "memory_key": escrow["memory_key"],
            "owner_id": escrow["owner_id"],
            "locked_by": escrow["locked_by"],
            "locked_at": escrow["locked_at"],
            "version": escrow["version"],
            "authorized_agents": list(escrow["authorized_agents"])
        }


class A2ARegistry:
    """
    Agent registry for discovery and capability matching.
    """
    
    def __init__(self):
        self._agents: Dict[str, AgentIdentity] = {}
        self._capabilities: Dict[str, Set[str]] = defaultdict(set)  # capability -> agent_ids
        self._handlers: Dict[str, Callable] = {}  # agent_id -> message handler
    
    def register(self, identity: AgentIdentity, 
                 message_handler: Optional[Callable] = None) -> bool:
        """Register an agent with the A2A network."""
        self._agents[identity.agent_id] = identity
        
        # Index capabilities
        for cap in identity.capabilities:
            self._capabilities[cap.name].add(identity.agent_id)
        
        if message_handler:
            self._handlers[identity.agent_id] = message_handler
        
        return True
    
    def unregister(self, agent_id: str) -> bool:
        """Remove agent from registry."""
        if agent_id not in self._agents:
            return False
        
        identity = self._agents[agent_id]
        for cap in identity.capabilities:
            self._capabilities[cap].discard(agent_id)
        
        del self._agents[agent_id]
        if agent_id in self._handlers:
            del self._handlers[agent_id]
        
        return True
    
    def discover(self, capability: Optional[str] = None,
                 status: Optional[str] = None) -> List[AgentIdentity]:
        """Discover agents by capability and/or status."""
        candidates = set(self._agents.keys())
        
        if capability:
            candidates = candidates & self._capabilities.get(capability, set())
        
        results = []
        for agent_id in candidates:
            agent = self._agents[agent_id]
            if status is None or agent.status == status:
                results.append(agent)
        
        return results
    
    def get_agent(self, agent_id: str) -> Optional[AgentIdentity]:
        """Get agent by ID."""
        return self._agents.get(agent_id)
    
    def update_status(self, agent_id: str, status: str) -> bool:
        """Update agent status."""
        if agent_id not in self._agents:
            return False
        
        self._agents[agent_id].status = status
        self._agents[agent_id].last_seen = datetime.now()
        return True
    
    def route_message(self, envelope: A2AEnvelope) -> Optional[A2AEnvelope]:
        """Route message to recipient handler."""
        recipient = envelope.recipient_id
        
        if recipient not in self._handlers:
            return None
        
        try:
            response = self._handlers[recipient](envelope)
            if response and isinstance(response, A2AEnvelope):
                return response
            return None
        except Exception as e:
            # Return error response
            return A2AEnvelope(
                message_id=str(uuid.uuid4()),
                message_type=MessageType.RESPONSE,
                sender_id=recipient,
                recipient_id=envelope.sender_id,
                timestamp=datetime.now(),
                correlation_id=envelope.message_id,
                payload={"error": str(e), "status": "failed"}
            )


class A2AProtocol:
    """
    Main A2A protocol implementation.
    Combines registry, escrow, and message routing.
    """
    
    def __init__(self, secret: Optional[str] = None):
        self.registry = A2ARegistry()
        self.escrow = A2AMemoryEscrow()
        self.secret = secret or str(uuid.uuid4())
        self._message_log: List[A2AEnvelope] = []
        self._pending_handoffs: Dict[str, Dict] = {}
    
    def create_message(self, sender_id: str, recipient_id: str,
                       message_type: MessageType, payload: Dict[str, Any],
                       correlation_id: Optional[str] = None,
                       sign: bool = True) -> A2AEnvelope:
        """Create a new A2A message envelope."""
        envelope = A2AEnvelope(
            message_id=str(uuid.uuid4()),
            message_type=message_type,
            sender_id=sender_id,
            recipient_id=recipient_id,
            timestamp=datetime.now(),
            correlation_id=correlation_id,
            payload=payload
        )
        
        if sign:
            envelope.sign(self.secret)
        
        return envelope
    
    def send(self, envelope: A2AEnvelope) -> Optional[A2AEnvelope]:
        """Send message through protocol."""
        # Verify if signed
        if envelope.signature and not envelope.verify(self.secret):
            raise ValueError("Message signature verification failed")
        
        self._message_log.append(envelope)
        
        # Handle special message types
        if envelope.message_type == MessageType.DELEGATE:
            return self._handle_delegate(envelope)
        elif envelope.message_type == MessageType.HANDOFF:
            return self._handle_handoff(envelope)
        elif envelope.message_type == MessageType.ESCROW:
            return self._handle_escrow_message(envelope)
        elif envelope.message_type == MessageType.DISCOVER:
            return self._handle_discover(envelope)
        
        # Route to recipient
        return self.registry.route_message(envelope)
    
    def _handle_delegate(self, envelope: A2AEnvelope) -> A2AEnvelope:
        """Handle delegation request."""
        task = envelope.payload.get("task", {})
        requirements = envelope.payload.get("requirements", [])
        
        # Find capable agents
        candidates = []
        for req in requirements:
            agents = self.registry.discover(capability=req)
            candidates.extend(agents)
        
        if not candidates:
            return self.create_message(
                sender_id="system",
                recipient_id=envelope.sender_id,
                message_type=MessageType.RESPONSE,
                payload={"error": "No capable agents found", "status": "failed"},
                correlation_id=envelope.message_id
            )
        
        # Select best candidate (simple: first available)
        selected = candidates[0]
        
        # Create delegation message
        delegate_msg = self.create_message(
            sender_id=envelope.sender_id,
            recipient_id=selected.agent_id,
            message_type=MessageType.REQUEST,
            payload={
                "delegated_task": task,
                "original_sender": envelope.sender_id,
                "delegation_context": envelope.payload.get("context", {})
            },
            correlation_id=envelope.message_id
        )
        
        return delegate_msg
    
    def _handle_handoff(self, envelope: A2AEnvelope) -> A2AEnvelope:
        """Handle conversation handoff."""
        handoff_mode = HandoffMode[envelope.payload.get("mode", "TEMPORARY")]
        context = envelope.payload.get("context", {})
        new_agent_id = envelope.payload.get("new_agent_id")
        
        if not new_agent_id:
            return self.create_message(
                sender_id="system",
                recipient_id=envelope.sender_id,
                message_type=MessageType.RESPONSE,
                payload={"error": "No target agent specified", "status": "failed"},
                correlation_id=envelope.message_id
            )
        
        # Store pending handoff
        handoff_id = str(uuid.uuid4())
        self._pending_handoffs[handoff_id] = {
            "from": envelope.sender_id,
            "to": new_agent_id,
            "mode": handoff_mode,
            "context": context,
            "timestamp": datetime.now()
        }
        
        # Notify receiving agent
        handoff_notify = self.create_message(
            sender_id=envelope.sender_id,
            recipient_id=new_agent_id,
            message_type=MessageType.NOTIFY,
            payload={
                "handoff_id": handoff_id,
                "mode": handoff_mode.name,
                "context": context if handoff_mode != HandoffMode.PARTIAL else {},
                "previous_agent": envelope.sender_id
            }
        )
        
        return handoff_notify
    
    def _handle_escrow_message(self, envelope: A2AEnvelope) -> A2AEnvelope:
        """Handle escrow operations."""
        action = EscrowAction[envelope.payload.get("action", "LOCK")]
        escrow_id = envelope.payload.get("escrow_id")
        agent_id = envelope.sender_id
        
        result = False
        if action == EscrowAction.LOCK:
            result = self.escrow.lock(escrow_id, agent_id)
        elif action == EscrowAction.RELEASE:
            result = self.escrow.commit(escrow_id, agent_id)
        elif action == EscrowAction.ROLLBACK:
            version = envelope.payload.get("version")
            result = self.escrow.rollback(escrow_id, agent_id, version)
        
        return self.create_message(
            sender_id="system",
            recipient_id=agent_id,
            message_type=MessageType.RESPONSE,
            payload={"action": action.name, "success": result, "escrow_id": escrow_id},
            correlation_id=envelope.message_id
        )
    
    def _handle_discover(self, envelope: A2AEnvelope) -> A2AEnvelope:
        """Handle capability discovery."""
        capability = envelope.payload.get("capability")
        agents = self.registry.discover(capability=capability, status="active")
        
        return self.create_message(
            sender_id="system",
            recipient_id=envelope.sender_id,
            message_type=MessageType.RESPONSE,
            payload={
                "agents": [
                    {
                        "id": a.agent_id,
                        "name": a.name,
                        "capabilities": [c.to_dict() for c in a.capabilities]
                    }
                    for a in agents
                ]
            },
            correlation_id=envelope.message_id
        )
    
    def get_message_history(self, agent_id: Optional[str] = None,
                           message_type: Optional[MessageType] = None) -> List[A2AEnvelope]:
        """Get message history with optional filters."""
        results = self._message_log
        
        if agent_id:
            results = [m for m in results 
                      if m.sender_id == agent_id or m.recipient_id == agent_id]
        
        if message_type:
            results = [m for m in results if m.message_type == message_type]
        
        return results


def create_a2a_protocol(secret: Optional[str] = None) -> A2AProtocol:
    """Factory function to create A2A protocol instance."""
    return A2AProtocol(secret=secret)
