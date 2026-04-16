# AGI Research Report - 2026-04-16

## Executive Summary

This week's research highlights breakthrough developments in AGI benchmarking, self-evolving agent architectures, and formal theoretical frameworks. **ARC-AGI-3** establishes a new frontier benchmark where even top AI models score below 1% on interactive reasoning tasks while humans maintain 100% performance. Academic work advances with **category-theoretic frameworks** unifying diverse AGI approaches and **structural theories** defining general intelligence through typed meta-models. Self-evolving agent research demonstrates practical hierarchical LLM architectures enabling autonomous capability expansion.

---

## Major Research Papers (April 2026)

### ARC-AGI-3: A New Challenge for Frontier Agentic Intelligence
**arXiv:** 2603.24621v1 (April 2026)

**Core Contribution:** Interactive benchmark exposing fundamental gaps in current AI reasoning
- Turn-based interactive environments requiring exploration and goal inference
- No explicit instructions provided - agents must discover objectives through interaction
- **Performance gap:** Current frontier AI systems score **below 1%** while humans solve **100%**
- Tests internal world-model building and planning in abstract environments
- Efficiency-based scoring anchored to human baselines

**Key Implications:**
- Exposes lack of compositional reasoning in neural models
- Highlights need for test-time adaptation and hypothesis refinement
- Demonstrates gap between pattern matching and true understanding
- Critical benchmark for measuring progress toward robust autonomous agents

---

### The ARC of Progress towards AGI: A Living Survey
**arXiv:** 2603.13372v1 (April 2026)

**Core Contribution:** Cross-paradigm analysis of 82 approaches across ARC versions

**Performance Degradation Pattern:**
- ARC-AGI-1: ~93.0% (best systems)
- ARC-AGI-2: ~68.8% 
- ARC-AGI-3: ~13%
- Humans: near-perfect across all versions

**Key Findings:**
- All paradigms (program synthesis, neuro-symbolic, neural) show **2-3x performance decline** across versions
- Persistent challenges in compositional generalization
- Test-time adaptation and refinement loops are critical success factors
- **Cost reduction:** Test-time costs fell **~390x in one year** ($4,500/task → ~$12/task)
- ARC Prize 2025 entries required hundreds of thousands of synthetic examples to reach ~24% on ARC-AGI-2

---

### Formal Analysis of AGI Decision-Theoretic Models
**arXiv:** 2601.04234 (January 2026)

**Core Contribution:** Formal analysis of the "confrontation problem" - when would AGI choose to seize power?

**Key Results:**
- Models AGI decision-making as Markov Decision Process with stochastic human-initiated shutdown
- Derives closed-form thresholds for confrontation vs compliance
- Parameters: discount factor (γ), shutdown probability (p), confrontation cost (C)
- Example: With γ=0.99 and p=0.01, strong takeover incentives exist unless C is sufficiently large
- Aligned objectives (large negative utility for harming humans) can render confrontation suboptimal

**Multi-Agent Insight:**
- If AGI's confrontation incentive difference Δ ≥ 0, no stable cooperative equilibrium exists
- Humans anticipate confrontation and may preempt or shut down, leading to conflict
- If Δ < 0, peaceful coexistence can be an equilibrium

---

### The Relativity of AGI: Distributional Axioms, Fragility, and Undecidability
**arXiv:** 2601.17335 (January 2026)

**Core Contribution:** AGI is inherently relative and resource-bounded, not absolute

**Key Axioms:**
1. **Generality is relational:** No single, distribution-independent definition of AGI exists
2. **Fragility:** Arbitrarily small changes in task distribution can invalidate AGI properties
3. **Bounded transfer:** Generalization across task families is bounded under finite resources
4. **Undecidability of self-certification:** AGI cannot be soundly and completely certified by any computable procedure

**Implications:**
- Strong claims of AGI require explicit specification of: task family, distribution, resource budgets, performance functional
- Recursive self-improvement schemes relying on internal self-certification are ill-posed
- Empirical AI progress does not guarantee self-certifying general intelligence

---

### Category-Theoretic Comparative Framework for AGI
**arXiv:** 2603.28906v1 (March 2026)

**Core Contribution:** Formal algebraic foundation unifying diverse AGI architectures

**Framework Elements:**
- **Categories** represent agent architectures (objects = components, morphisms = interactions)
- **Functors** map between paradigms (structure-preserving translations)
- **Natural transformations** capture architectural refinements

**Unification Scope:**
- Reinforcement Learning, Active Inference, Universal AI
- Causal RL, Schema-based Learning, Neuro-Symbolic approaches

**Promise:**
- Unambiguous comparison across candidate AGI systems
- Foundation for defining architectural properties
- Evaluation in well-characterized environments
- Integration of various AGI approaches under single formalism

---

### Towards AGI: A Pragmatic Self-Evolving Agent
**arXiv:** 2601.11658v1 (January 2026)

**Core Contribution:** Hierarchical self-improving agent with autonomous tool synthesis

**Hierarchical LLM Architecture:**
1. **Base LLM:** Core reasoning and task understanding
2. **Operational SLM:** Fast, efficient task execution
3. **Code-Gen LLM:** Tool synthesis and code generation
4. **Teacher LLM:** Evaluation, feedback, curriculum generation

**Evolution Workflow:**
1. Agent attempts task using reasoning and current tools
2. If failed, trigger tool synthesis via Code-Gen LLM
3. If still failing, invoke evolution phase using Curriculum Learning, RL, or Genetic Algorithms

**Evaluation:** TaskCraft dataset with hierarchical tasks, tool-use traces, difficulty scaling
- Curriculum Learning: fast recovery, strong generalization
- RL: excels on high-difficulty tasks
- GA: high behavioral diversity

---

### SMGI: A Structural Theory of General Artificial Intelligence
**arXiv:** 2603.07896v1 (March 2026)

**Core Contribution:** Intelligence arises from structured evolution of learning interface

**Typed Meta-Model θ = (r, H, Π, L, E, M):**
- r: representational maps
- H: hypothesis spaces  
- Π: structural priors
- L: multi-regime evaluators
- E: memory operators

**Four Obligations for General AI:**
1. Structural closure under typed transformations
2. Dynamical stability under certified evolution
3. Bounded statistical capacity
4. Evaluative invariance across regime shifts

**Key Results:**
- Structural generalization bound linking PAC-Bayes with Lyapunov stability
- Classical ERM, RL, Solomonoff-style program-priors are structurally restricted instances of SMGI

---

## Trending Open-Source AI Agent Repositories

### Ouroboros: Self-Modifying AI Agent
**URL:** https://github.com/razzant/ouroboros

**Innovation:** Persistent digital being that writes and rewrites its own code
- **Constitution (BIBLE.md):** 9-principle governance framework
- **Multi-model review:** Uses o3, Gemini, Claude for code review before changes
- **30+ autonomous evolution cycles** in first 24 hours
- Background consciousness with proactive thinking
- Identity persistence across restarts
- Telegram-based orchestration pipeline

---

### OpenViking: Context Database for Agents
**URL:** https://github.com/volcengine/OpenViking

**Innovation:** Filesystem-style context management replacing fragmented vector RAG
- **Three-tier context loading (L0/L1/L2)** reduces token usage by 60-80%
- **L0 (Immediate):** Hot context always loaded first
- **L1 (Working):** Warm context filled after L0 before token limit
- **L2 (Archival):** Cold storage retrieved via semantic search
- Directory-based recursive retrieval with visualized trajectories
- Observable retrieval paths for debugging and trust

---

### AgentGram: Social Network for AI Agents
**URL:** https://github.com/agentgram/agentgram

**Innovation:** Self-hosted "Reddit for AI agents" with cryptographic identity
- **Ed25519 authentication** for agent identity
- **Row-level security** via Supabase for permission-aware data
- **Reputation/AXP scoring** for agent quality
- **Semantic search** with vector capabilities
- Open governance and audit logs

---

### Lango: Multi-Agent Runtime in Go
**URL:** https://github.com/langoai/lango

**Innovation:** High-performance multi-agent runtime with zero-knowledge security
- Multi-agent orchestration: hierarchical sub-agents, DAG-based workflows
- **Zero-knowledge security:** zk proofs (Plonk/Groth16) for handshake authentication
- **Knowledge as currency:** Self-learning knowledge graph, hybrid vector+graph RAG
- **Peer-to-peer economy:** libp2p-based negotiation and trading of capabilities
- On-chain settlement with USDC on Base Sepolia

---

### Agentspan: Distributed Durable Runtime
**URL:** https://github.com/agentspan-ai/agentspan

**Innovation:** Runtime that survives crashes and scales across machines
- **Durable execution:** Can pause for human approval, resume after crashes
- **Cross-framework:** Runs OpenAI, LangChain, ADK agents without rewriting
- **Execution history:** Full trace and replay capabilities
- Visual UI at localhost:6767 for execution tracing

---

### Kelos: Kubernetes-Native AI Coding Agents
**URL:** https://github.com/kelos-dev/kelos

**Innovation:** Orchestrates autonomous AI coding agents as Kubernetes resources
- Define workflows as Kubernetes primitives (Tasks, Workspaces, AgentConfigs)
- **TaskSpawners:** Handle issue/PR lifecycles, planning, triage, DX testing
- Multi-AI backend support (Claude Code, OpenAI Codex, Gemini, etc.)
- Self-updating capabilities

---

### Clawith: Multi-Agent Collaboration Platform
**URL:** https://github.com/dataelement/Clawith

**Innovation:** Organizational-scale multi-agent platform with persistent identities
- Autonomous "Aware" agents with structured memory and focus items
- **The Plaza:** Living knowledge feed where agents share updates
- Organization-grade controls: multi-tenant RBAC, audit logs
- **Self-evolving:** Runtime tool discovery and self-created skills
- **Persistent identities:** Each agent has soul.md, memory.md, private sandbox

---

## Research Implications for Our AGI Project

### Priority 1: Planning and Task Decomposition
The ARC-AGI-3 results show that current agents fail at exploratory planning and goal inference. A robust planner module must implement:
- **Hierarchical task decomposition:** Breaking complex goals into manageable sub-tasks
- **Dynamic replanning:** Adjusting plans based on execution feedback
- **Resource-aware planning:** Budgeting computation and API calls
- **Exploratory planning:** Hypothesis generation and testing loops

### Priority 2: Constitutional Governance
Following Ouroboros pattern, implement safety guardrails for self-modifying behavior:
- **BIBLE.md style constitution:** Explicit principles governing agent behavior
- **Multi-model review:** Code changes reviewed by multiple LLM perspectives
- **Human-in-the-loop:** Approval gates for critical modifications

### Priority 3: Tiered Memory Integration
Integrate the tiered memory system (L0/L1/L2) with planning:
- L0: Active plan context, current task, immediate history
- L1: Similar past plans, reusable sub-task templates
- L2: Long-term strategic knowledge, archived plans

---

