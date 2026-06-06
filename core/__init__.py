"""
Core AGI System Components

This module provides the foundational components for building AGI-capable agents:
- BaseAgent: Core agent with EXPLORE/VERIFY/PLAN/EXECUTE/REFLECT cycle
- MemoryManager: Hierarchical memory (working, episodic, semantic)
- Planner: Task decomposition and parallel execution planning
- ReflectionEngine: Self-correction and learning from execution
"""

from .agent import BaseAgent, AgentState, Thought, Action, ExecutionResult
from .memory import MemoryManager, MemoryEntry
from .planner import Planner, PlanNode, ExecutionPlan
from .reflection import ReflectionEngine, ReflectionResult
from .evidence_ledger import (
    Claim,
    ClaimStatus,
    ClaimVerification,
    Evidence,
    EvidenceKind,
    EvidenceLedger,
    EvidencePolarity,
    LedgerSummary,
    create_ledger,
)
from .trace_grounding import (
    StepGrounding,
    TraceGrounder,
    TraceGroundingReport,
    ground_trace,
)

__all__ = [
    "BaseAgent",
    "AgentState",
    "Thought",
    "Action",
    "ExecutionResult",
    "MemoryManager",
    "MemoryEntry",
    "Planner",
    "PlanNode",
    "ExecutionPlan",
    "ReflectionEngine",
    "ReflectionResult",
    "Claim",
    "ClaimStatus",
    "ClaimVerification",
    "Evidence",
    "EvidenceKind",
    "EvidenceLedger",
    "EvidencePolarity",
    "LedgerSummary",
    "create_ledger",
    "StepGrounding",
    "TraceGrounder",
    "TraceGroundingReport",
    "ground_trace",
]
