# AGI Research - Current Findings

**Research Date:** 2026-04-30  
**Session:** AGI Continuous Research & Build Agent

---

## 🔬 Phase 1: Research Summary

### 1. Latest AGI Research Breakthroughs (Week of 2026-04-30)

#### Key Developments:

**Appier AI Self-Awareness Research** [^1]
- New research focused on AI self-awareness for trustworthy Agentic AI
- Four research capabilities position Agentic AI as trustworthy decision partner
- Current deployments block 80% of risky responses for enterprise users
- Risk-aware decision framework for enterprise scenarios

**Microsoft-OpenAI Partnership Restructuring** [^2]
- New agreement extends Microsoft's IP rights through 2030 (previously would terminate at AGI declaration)
- Removes the AGI cap that would have cut off Microsoft access
- Revenue-share payments capped but continue at same percentage through 2030
- Reflects shifting definitions of AGI milestones

**FINGERS-7B: AI for Alzheimer's Prevention** [^3]
- First AI foundation model designed specifically to prevent Alzheimer's disease
- Achieves 4× more accurate preclinical diagnosis
- Integrates lifestyle, genomics, and proteomics data
- Can identify disease up to a decade before symptoms appear

---

### 2. AI Agent Architecture Trends 2026

#### Emerging Patterns:

**Multi-Agent Workflow Architecture** [^4]
- 2026 enterprise systems feature:
  - Multi-agent workflows
  - Tool access via MCP (Model Context Protocol)
  - Agent communication via A2A (Agent-to-Agent)
  - Orchestration layers like LangGraph

**Core Architecture Paradigms:**
1. **Graph-based** → agents as nodes, transitions as edges (LangGraph)
2. **Role-based** → agents as job titles on a team (CrewAI)
3. **Code-execution** → agent writes and runs Python as its action (Smolagents)
4. **Conversation-based** → agents communicate via dialogue (AutoGen)

**Production Multi-Agent Patterns** [^5]:
- Pipeline architecture: sequential task decomposition
- Hierarchical architecture: orchestrator + sub-agents
- Peer-to-peer architecture: agent collaboration networks
- Living specifications: shared goal state for coordination

#### Top Frameworks 2026:

| Framework | Approach | Key Feature |
|-----------|----------|-------------|
| LangGraph | Graph-based | Deterministic state transitions |
| CrewAI | Role-based | Low barrier to entry (~20 lines) |
| AutoGen | Conversation | Multi-agent dialogue |
| Smolagents | Code-execution | Python-native actions |
| Microsoft Agent Framework | Graph-based | Time-travel, checkpointing |

---

### 3. arXiv Papers (Past 2 Weeks)

#### Key Papers Identified:

**1. "ARC-AGI-2 Technical Report" (arXiv:2603.06590v1)** [^6]
- Transformer-based system for ARC-style generalization
- Test-time training (TTT) with LoRA adaptation
- Symmetry-aware decoding and scoring
- Closing gap toward human-level generalization

**2. "SMGI: A Structural Theory of General Artificial Intelligence" (arXiv:2603.07896v1)** [^7]
- Proposes SMGI: learning as evolving the learning interface
- Typed meta-model θ = (r, H, Π, L, E, M)
- Four obligations for general AI:
  1. Structural closure under typed transformations
  2. Dynamical stability under certified evolution
  3. Bounded statistical capacity
  4. Evaluative invariance across regime shifts
- Unifying framework for ERM, RL, Solomonoff priors, agentic systems

**3. "The Geometry of Benchmarks: A New Path Toward AGI" (arXiv:2512.04276)** [^8]
- Geometric framework treating benchmarks as moduli space
- Autonomous AI (AAI) Scale (Kardashev-style autonomy)
- Generator-Verifier-Updater (GVU) operator
- Self-improvement coefficient κ as Lie derivative

**4. "LLM-in-Sandbox Elicits General Agentic Intelligence" (arXiv:2601.16206v2)** [^9]
- LLM operates inside code sandbox for agentic capabilities
- Training-free agentic behavior emergence
- Generalization across: math, physics, chemistry, biomedicine
- Open-sourced as Python package

**5. "SuperARC: A Test for General and Super Intelligence" (arXiv:2503.16743v1)** [^10]
- Open-ended framework using recursion theory and algorithmic probability
- Avoids benchmark contamination
- Hybrid neurosymbolic approach shows promise vs pure LLMs

**6. "The ARC of Progress towards AGI: A Living Survey" (arXiv:2603.13372v1)** [^11]
- Analysis of 82 approaches across ARC-AGI versions 1-3
- Performance drops 2-3× from ARC-AGI-1 to ARC-AGI-2
- Test-time adaptation critical for success
- Compositional reasoning remains unsolved

---

### 4. Trending Open-Source AI Agent Repos (GitHub)

#### Top Repositories:

**1. OpenAI Agents SDK (openai/openai-agents-python)** [^12]
- ⭐ 7k+ stars, 260+ contributors
- Lightweight, provider-agnostic framework
- Features: sandbox agents, guardrails, handoffs, tracing
- Supports 100+ LLMs beyond OpenAI
- Latest: v0.14.8 (Apr 2026)

**2. VoltAgent (voltagent/voltagent)** [^13]
- ⭐ 7k+ stars, TypeScript-first
- End-to-end platform with VoltOps console
- Memory, workflows, supervisors/sub-agents, MCP integration
- Built-in observability and evaluation
- Latest: v2.1.11 (Apr 2026)

**3. Microsoft Agent Framework (microsoft/agent-framework)** [^14]
- Multi-language (Python, C#/.NET)
- Graph-based workflows, checkpointing, time-travel
- Human-in-the-loop, streaming
- Active development (130+ contributors)
- Latest: python-1.2.2 (Apr 2026)

**4. Agent Zero (agent0ai/agent-zero)** [^15]
- General-purpose autonomous agent framework
- Skills System (SKILL.md standard)
- Git-based project workspaces
- ~50 releases, 40+ contributors
- Latest: v1.9 (Apr 2026)

**5. OpenAkita (openakita/openakita)** [^16]
- Multi-agent AI assistant framework
- Organization-level orchestration (CEO/CTO roles)
- 30+ LLMs, 6 IM platforms, 89+ tools
- 6-layer sandbox security
- Latest: v1.27.9 (Apr 2026)

**6. Multica (multica-ai/multica)** [^17]
- Vendor-neutral autonomous coding agents
- Agent lifecycle management
- Real-time progress via WebSocket
- Multiple runtimes (local/cloud)
- Latest: v0.2.16 (Apr 2026)

**7. Upsonic (Upsonic/Upsonic)** [^18]
- Production-ready with Safety Engine
- OCR capabilities for document analysis
- Policy-driven safety, multi-agent teams
- Latest: v0.72.5

---

## 🔧 Phase 2: Repo Structure Status

### Current State:
- ✅ Directory structure created
- ✅ CURRENT_RESEARCH.md populated
- ⏳ README.md - to be created
- ⏳ ARCHITECTURE.md - to be created
- ⏳ Core modules - to be implemented
- ⏳ Skills modules - to be implemented
- ⏳ Experiments - to be created

### Directory Structure:
```
agi-research/
├── README.md
├── CURRENT_RESEARCH.md
├── ARCHITECTURE.md
├── core/
│   ├── agent.py
│   ├── memory.py
│   ├── planner.py
│   └── reflection.py
├── skills/
│   └── [capability modules]
└── experiments/
    └── [validation tests]
```

---

## 🏗️ Phase 3: Build Task Selected

### Priority: Implement Core Memory Module

**Rationale:**
- Memory is foundational for all other components
- Research shows memory critical for:
  - Test-time adaptation (ARC-AGI findings)
  - Long-horizon control (AAI Scale)
  - Compositional reasoning
- Multiple memory types needed:
  - Working/short-term memory
  - Long-term episodic memory
  - Semantic memory (facts/knowledge)
  - Procedural memory (skills)

**Implementation Plan:**
1. Create `core/memory.py` with base memory interface
2. Implement memory adapters (in-memory, file-based)
3. Add context window management
4. Create memory retrieval with relevance scoring
5. Write tests in `experiments/test_memory.py`

---

## 📝 Key Research Insights for Implementation

### 1. Memory Architecture Insights
From LLM-in-Sandbox paper [^9]:
- Long context management via filesystem abstraction
- Memory as tool-use pattern
- Sandboxing enables safe memory operations

From SMGI paper [^7]:
- Learning interface evolves, not just hypotheses
- Bounded statistical capacity constraint
- Evaluative invariance across regime shifts

### 2. Multi-Agent Patterns to Adopt
From Microsoft Agent Framework [^14]:
- Graph-based state management
- Checkpointing for fault tolerance
- Time-travel debugging

From VoltAgent [^13]:
- Durable memory adapters
- Tool registry with MCP integration
- Built-in observability

### 3. Evaluation Insights
From ARC-AGI survey [^11]:
- Test-time adaptation is critical
- Compositional reasoning is the bottleneck
- Efficiency matters (skill-acquisition efficiency correlates with intelligence)

---

## 🎯 Next Priority

### Immediate Next Steps:
1. ✅ Complete Phase 1 & 2 (Research, Repo Structure)
2. 🔄 Implement `core/memory.py` (Phase 3)
3. ⏳ Implement `core/agent.py` base class
4. ⏳ Add web search skill module
5. ⏳ Create first experiment: Memory stress test

### Long-term Goals:
- Build toward SMGI-inspired structural learning
- Implement GVU (Generator-Verifier-Updater) loop
- Create ARC-AGI style reasoning tests
- Develop multi-agent orchestration

---

## 📚 References

[^1]: https://www.prnewswire.com/news-releases/appier-advances-ai-self-awareness-to-unlock-enterprise-roi-302757039.html
[^2]: https://www.theverge.com/ai-artificial-intelligence/918981/openai-microsoft-renegotiate-contract
[^3]: https://neurosciencenews.com/fingers-7b-alzheimers-ai-model-30629/
[^4]: https://www.reddit.com/r/AI_Agents/comments/1t00nll/agentic_ai_architecture_in_2026/
[^5]: https://www.augmentcode.com/guides/multi-agent-ai-systems
[^6]: https://arxiv.org/abs/2603.06590v1
[^7]: https://arxiv.org/abs/2603.07896v1
[^8]: https://arxiv.org/abs/2512.04276
[^9]: https://arxiv.org/abs/2601.16206v2
[^10]: https://arxiv.org/abs/2503.16743v1
[^11]: https://arxiv.org/abs/2603.13372v1
[^12]: https://github.com/openai/openai-agents-python
[^13]: https://github.com/voltagent/voltagent/
[^14]: https://github.com/microsoft/agent-framework
[^15]: https://github.com/agent0ai/agent-zero/
[^16]: https://github.com/openakita/openakita
[^17]: https://github.com/multica-ai/multica
[^18]: https://github.com/Upsonic/Upsonic
