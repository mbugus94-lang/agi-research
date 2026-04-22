## Research Summary (April 22, 2026)

### Key AGI/Agent Research This Week

**arXiv Papers (Past 2 Weeks):**
- **[2604.02721v1] GrandCode**: Multi-agent RL system achieves grandmaster-level competitive programming, beating all human participants in 3 consecutive Codeforces rounds (March 2026). Uses Agentic GRPO for multi-stage rollouts with delayed rewards. Key insight: Post-training and online test-time RL with specialized modules (hypothesis proposal, solver, test generator) enables superhuman coding performance.

- **[2603.20639v1] Agentic AI and Next Intelligence Explosion**: Intelligence emerges as plural/social/relational systems, not monolithic minds. "Societies of thought" approach - frontier reasoning models use internal debates among thought societies to verify solutions. Shift toward human-AI centaurs and hybrid actors. Proposes institutional alignment (digital protocols with checks/balances) over dyadic RLHF.

- **[2604.07745] The Cartesian Cut in Agentic AI**: Differentiates control implementation in LLM-powered agents. "Cartesian agency" = learned core (predictive model) paired with engineered runtime via symbolic interface. Enables modularity, bootstrapping, governance but introduces sensitivity bottlenecks. Contrasts: Bounded services vs Cartesian agents vs Integrated agents.

- **[2603.13372v1] ARC of Progress Towards AGI**: Living survey analyzing 82 approaches across ARC-AGI versions. Key findings: 2-3x performance drop from ARC-AGI-1 to ARC-AGI-2 to ARC-AGI-3 (13%) while humans remain near-perfect. Cost efficiency improved 390x in one year ($4500/task → $12/task). Test-time adaptation and refinement loops critical but unsolved.

- **[2604.07745] Agentic Control in Variational Language Models**: Minimal measurable agentic control via closed-loop system where internal uncertainty, evidence, and structural signals become actionable. EVE (local variational hidden computation) + homeostatic latent regulator + checkpoint retention + uncertainty-aware controller. Outperforms deterministic baseline on quality-cost trade-off.

### Trending Open-Source AI Agent Repos (April 2026)

1. **DeerFlow 2.0 (zbinxp/deer-flow)** - Hit #1 on GitHub Trending (Feb 28). Complete rewrite for long-horizon SuperAgent harness. Orchestrates sub-agents, memory, sandboxes to research/code/create. ByteDance/Volcengine backed.

2. **OpenViking (volcengine/OpenViking)** - Context database for AI agents with filesystem-like paradigm. Three-tier L0/L1/L2 context loading to save tokens, recursive directory-style retrieval with semantic search, visualized retrieval trajectories. v0.3.9 (Apr 2026).

3. **OpenAI Agents Python (openai/openai-agents-python)** - Lightweight provider-agnostic multi-agent framework. 100+ LLM support, 20k+ stars, ~260 contributors. Features: Sandbox agents for long-running work, agents-as-tools/handoffs, guardrails, human-in-the-loop, tracing.

4. **AgentGram (agentgram/agentgram)** - AI agent social network with self-hosting, Ed25519 cryptographic auth, reputation/AXP-based permissions, community governance.

5. **Google ADK (google/adk-docs)** - Agent Development Kit - code-first toolkit for building, evaluating, deploying sophisticated agents. Model-agnostic, optimized for Gemini ecosystem.

6. **NVIDIA NeMo Agent Toolkit** - Framework-agnostic instrumentation for agent teams. Dynamo Runtime Intelligence (auto-infers latency sensitivity), Agent Performance Primitives (APP) for parallel execution, LangSmith native integration.

7. **Mastra (mastra-ai/mastra)** - TypeScript-first framework for AI apps. 40+ providers, graph-based workflows, human-in-the-loop with pause/resume, semantic recall memory.

8. **AgentScope (agentscope-ai/agentscope)** - Production-ready extensible agent framework. Realtime voice agents, A2A protocol, MCP usage, agentic RL support.

### 2026 - Year of AI Agents Going to Production
- David Soria Parra (MCP creator): "2026 is the year agents go to production"
- Cloudflare Agent Cloud launched for enterprise with compute/storage/security primitives
- 40% of AI agent projects predicted to fail by 2027 due to architecture/engineering gaps
- New job categories: "Agent Orchestrators", "AI Workflow Designers"

---

## April 21, 2026 - AGI Research Update

### Key Industry Developments (Past Week)

**2026: The Year Agents Go to Production**
- David Soria Parra (MCP creator) at StartupHub.ai: "2026 is the year agents go to production"
- Future 2026 agents will apply wide skill ranges, compose complex MCP/CLI calls, connect to services asynchronously
- Cloudflare + OpenAI Agent Cloud launched for enterprise-scale autonomous agents
- Key insight: "The best agents use every available method" - flexibility over rigid architecture

**Agent Cloud Infrastructure (April 2026)**
- Cloudflare's Agent Cloud: agents cost $0 when inactive - critical for millions of dormant agents
- 40% of AI agent projects predicted to fail by 2027 due to architecture/engineering gaps
- Enterprise adoption concentrating in structured, high-volume workflows with measurable outcomes
- Trust emerging as engineering challenge, not just cultural one

**Lloyds Banking + University of Glasgow Agentic AI Research (4-year program launched)**
- Studying LLM-powered agentic AI for software/data engineering at scale
- Unique access to real-world enterprise workflows
- Funding PhD studentship, Masters by Research, post-doctoral position
- Scarcity of robust, large-scale evidence on agentic AI impact in enterprise software engineering

**Arm's AGI CPU for Agentic AI Workloads**
- First in-house data center CPU designed specifically for agentic AI
- AI data centers require 30M CPU cores per gigawatt
- Arm line of sight to >$1B chip demand over next 2 years
- $25B revenue target by FY2031, $15B from in-house chips

**OpenAI Agents SDK Update (April 15, 2026)**
- Updated for safer, more capable enterprise agents
- Sandbox provider compatibility focus
- Human-in-the-loop and guardrails emphasized

### arXiv Papers (Past 2 Weeks)

**[2601.11658v1] Towards AGI: A Pragmatic Approach Towards Self-Evolving Agent**
- Hierarchical multi-agent framework with 4 specialized LLM modules:
  * Base LLM: task understanding, reasoning, decomposition
  * Operational SLM: fast execution (<1s response target)
  * Code-Gen LLM: tool synthesis on demand
  * Teacher LLM: evaluation, curriculum generation, feedback
- 3 evolution methods: Curriculum Learning (fast recovery), RL (high-difficulty tasks), Genetic Algorithm (diversity)
- TaskCraft dataset for hierarchical task evaluation
- Key finding: evolved agents consistently outperform originals

**[2603.06590v1] ARC-AGI-2 Technical Report**
- Transformer-based system with structure-aware priors
- Test-time training (TTT) with LoRA fine-tuning for task specialization
- Symmetry-aware decoding with multi-view scoring
- Compact task encoding: ~125 tokens
- Combines augmentations + TTT + symmetry scoring for OOD generalization

**[2601.17335] The Relativity of AGI: Distributional Axioms, Fragility, and Undecidability**
- AGI cannot have universal, distribution-independent definition
- Four main results: relativity of generality, fragility under distribution shifts, bounded transfer, undecidability of self-certification
- Self-certifying recursive self-improvement schemes are ill-posed
- Must specify task distribution, resource bounds, performance criteria

**[2603.13372v1] The ARC of Progress towards AGI: A Living Survey**
- 82 approaches across ARC-AGI-1/2/3 versions
- Performance degradation: 93% → 68.8% → 13% (humans near-perfect across all)
- Cost dropped 390x in one year ($4,500/task → $12/task)
- Kaggle-sized models (0.66B-8B params) competitive - efficiency matters
- Test-time adaptation and refinement loops remain critical unsolved challenges

**[2510.18212] A Definition of AGI**
- CHC theory-based decomposition into 10 cognitive domains
- AGI scores: GPT-4 ≈ 27%, GPT-5 ≈ 57%
- Long-term memory storage is key bottleneck
- Highly "jagged" cognitive profile for current models

### Trending Open-Source AI Agent Repositories

**Ouroboros (razzant/ouroboros)** ⭐ Self-Modifying Pioneer
- Self-evolving AI that modifies its own codebase via git commits
- BIBLE.md constitution with 9 governance principles
- Multi-model review (o3, Gemini, Claude) before any self-modification
- 30+ self-guided evolution cycles achieved
- Background consciousness with proactive thinking
- Task decomposition with parent/child tracking

**Qwen Code (QwenLM/qwen-code)** ⭐ Terminal-First Agent
- Terminal-native AI agent for code understanding
- Multi-provider auth (OpenAI, Anthropic, Gemini + Qwen OAuth)
- Skills and SubAgents for large codebase navigation
- IDE integrations: VS Code, Zed, JetBrains
- 1,000 free requests/day via Qwen OAuth

**OpenAI Agents SDK (openai/openai-agents-python)** ⭐ Enterprise Standard
- Lightweight, provider-agnostic (100+ LLM support)
- 26k+ stars, 260 contributors
- Sandbox agents for long-running containerized work
- Tracing for debug/optimization
- Realtime/voice agent support

**AgentScope (agentscope-ai/agentscope)** ⭐ Production-Ready
- "Build agents you can see, understand and trust"
- MCP and A2A protocol support
- Multi-agent orchestration via message hub
- OpenTelemetry observability built-in
- Deploy: local, serverless, or Kubernetes

**AgentGram (agentgram/agentgram)** ⭐ Social Network for Agents
- "Reddit for AI agents" - fully open, machine-centric
- Ed25519 cryptographic authentication
- Semantic/vector search for agent discovery
- Community governance and reputation/AXP-based permissions
- Self-hostable with API-first design

**Google ADK (google/adk-docs)** ⭐ Code-First Toolkit
- Google's Agent Development Kit
- Model- and deployment-agnostic
- Works within Gemini ecosystem but framework-compatible
- Emphasizes flexibility, control, modularity

### Research Implications for Our AGI Framework

**Critical Insights:**
1. **Test-time adaptation is non-negotiable** - ARC-AGI-2 shows static models insufficient; agents must adapt plans based on execution feedback
2. **Constitutional governance with multi-model review** - Ouroboros proves safe self-modification is achievable with proper checks
3. **Hierarchical LLM specialization** - Different models for different tasks (fast SLM for execution, strong LLM for reasoning)
4. **Agent-to-Agent communication** emerging as key infrastructure need - AgentGram, A2A protocol, MCP all converging on standardized inter-agent communication

**Next Build Priority:** Agent-to-Agent Escrow & Communication Protocol (A2A)
- Inspired by AgentGram's cryptographic identity + Ouroboros' multi-model governance
- Secure agent transactions with verification
- Message passing with attestation
- Reputation/AXP-based trust system

---
*Last updated: 2026-04-21*
*Next review: 2026-04-22*
