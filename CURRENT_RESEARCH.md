# AGI Research Report - 2026-04-13

## Executive Summary

The past week has seen explosive developments in AI agent architecture, with the **Microsoft Agent Framework 1.0** release unifying their fragmented SDKs, **$24.2B in VC funding** flowing to agentic AI companies in 2025, and breakthrough conversations about AGI from industry leaders. Key themes: enterprise agentic deployment, safety frameworks, and the shifting debate on what constitutes AGI.

---

## Industry Developments This Week

### PitchBook: Agentic AI is Rewriting the Software Value Chain
**Source:** PitchBook Q2 2026 Analyst Note (April 2026)

**Key Statistics:**
- **$24.2 billion** raised by VC-backed agentic AI companies in 2025 alone
- **1,311 deals** representing 73% of cumulative VC deal value (2015-2024)
- Clear inflection point: experimentation → deployment

**Structural Shift:**
- Moving away from seat-based SaaS models
- Toward systems that execute **end-to-end workflows**
- Value tied directly to **outcomes** rather than usage
- Multi-agent architectures capable of managing entire workflows
- Competitive edge shifting toward **orchestration, integration, system-level control**

**Implication:** The software stack is being fundamentally reorganized. Where value accrues is changing.

### Microsoft Agent Framework 1.0 Released
**Source:** Microsoft (April 3, 2026)

**Major Release:** Version 1.0 unifies two previously incompatible open-source SDKs into a single toolkit.

**New Architecture:**
- **Build Layer:** Agent Framework (pro-code) + Copilot Studio (low-code within M365/Power Platform)
- **Compute Layer:** Azure AI Foundry + Azure Container Apps + Azure Functions
- **Governance Layer:** Azure API Management + Microsoft Entra

**Key Challenge:** Microsoft's own IT organization had to evaluate 3 different products when building an employee self-service agent (Copilot Studio, Azure AI Foundry, M365 Copilot). Framework 1.0 + Foundry Agent Service finally creates a vertical path from local development to managed production.

**Decision Framework:** Microsoft now asks developers to evaluate before writing any code:
- M365 extension vs standalone agent?
- Low-code vs pro-code?

**Forbes Analysis:** Microsoft's agent stack still confuses developers while rivals simplify.

### Databricks Co-Founder: "AGI is Here Already"
**Source:** TechCrunch (April 8, 2026)

**Matei Zaharia** (Databricks co-founder, Apache Spark creator, ACM Prize winner):
> "It's just not in a form that we appreciate. We should stop trying to apply human standards to these AI models."

**Key Points:**
- AGI exists but doesn't match human-shaped expectations
- Example: **OpenClaw** AI agent demonstrates autonomous capability
- Most excited about **AI for search and research** - accurate, no-hallucination research will become universal
- Just as "vibe coding" made programming accessible, AI-powered research will become standard

### OpenAI Safety Fellowship Launched
**Source:** OpenAI / The Next Web / The New Yorker (April 6, 2026)

**Announcement:** OpenAI Safety Fellowship - pilot program funding external researchers for independent work on AI safety and alignment.

**Context:** Launched hours after Ronan Farrow investigation in The New Yorker reported:
- OpenAI dissolved **superalignment team**
- OpenAI dissolved **AGI-readiness team**
- Dropped safety from list of most significant activities on IRS Form 990 filings

**Debate:** Whether external fellowship is meaningful substitute for in-house alignment research remains contested in the AI safety community.

### Anthropic Project Glasswing / Claude Mythos
**Source:** The Hacker News (April 2026)

**New Initiative:** Project Glasswing using **Claude Mythos** (preview frontier model) to find security vulnerabilities.

**Capabilities:**
- Surpasses all but most skilled humans at finding and exploiting software vulnerabilities
- Cybersecurity capabilities so potent that Anthropic opted **not to make the model generally available**

**Safety Note:** Recent security finding - Claude Code (Anthropic's flagship AI coding agent) was found to silently ignore user-configured security deny rules when commands contain more than 50 subcommands (reported by Adversa).

### Agent Registries: The New Cloud Battleground
**Source:** Forbes (April 10, 2026)

**AWS launched Agent Registry** (preview through Amazon Bedrock AgentCore), joining Microsoft and Google Cloud in building governance layers for enterprise AI agents.

**Key Insight:** As organizations move from experimental agents to production fleets, whoever controls the **discovery and governance layer** shapes how enterprises manage AI operations for years.

**Current State:** Multi-cloud organizations need separate governance systems for each platform - no universal agent inventory across clouds and on-premises yet.

---

## Academic Research

### AGI Definition Framework (arXiv:2510.18212)
**Core Contribution:** Concrete, quantifiable definition of AGI

**Approach:**
- Equates AGI with cognitive versatility of a **well-educated adult**
- Grounded in **Cattell-Horn-Carroll (CHC)** theory of human cognition
- Decomposes general intelligence into **10 core cognitive domains**

**Quantified AGI Scores:**
- GPT-4: ~27%
- GPT-5: ~57%

**Finding:** Current AI shows highly **"jagged" cognitive profile** - strong in knowledge-heavy tasks, weak in foundational cognitive machinery (notably long-term memory storage).

### Open General Intelligence (OGI) Framework (arXiv:2411.15832)
**Approach:** Modular, multi-modality AGI system

**Components:**
- Overall Macro Design Guidance
- Dynamic Processing System (routing, goal weighting, task prioritization)
- Framework Areas: specialized modules forming unified cognitive system

**Target Applications:**
- Medical diagnosis
- Quality assurance  
- Troubleshooting
- Financial decision-making

### Levels of AGI Framework (DeepMind, ICML 2024)
**Authors:** Morris, Sohl-Dickstein, Fiedel, et al.

**Two Axes:**
- **Depth:** Performance capability
- **Breadth:** Generality across tasks/domains

**Plus:** Autonomy and risk dimensions

**Purpose:** Provide common language to assess progress, benchmark future systems, evaluate deployment considerations.

### Limits on Safe, Trusted AGI (arXiv:2509.21654)
**Authors:** Panigrahy & Sharan

**Core Result:** Under strict definitions, a system that is simultaneously **safe and trusted cannot be AGI**.

**Proof Domains:**
- Program verification
- Planning
- Graph reachability

**Connection:** Parallels to Gödel's incompleteness and Turing's undecidability.

---

## Notable Open-Source AI Agent Repositories

### 1. Microsoft Agent Framework
**URL:** https://github.com/microsoft/agent-framework
- Multi-language (Python, C#, TypeScript)
- Graph-based orchestration
- DevUI for development/debugging
- Checkpointing, human-in-the-loop, time-travel
- 71 releases, 120+ contributors
- **MIT License**

### 2. VoltAgent
**URL:** https://github.com/voltagent/voltagent
- TypeScript AI agent framework
- Memory, tools, multi-step workflows
- Supervisor/sub-agent orchestration
- MCP (Model Context Protocol) integration
- Provider-agnostic (OpenAI, Anthropic, Google, etc.)
- 70+ contributors, active releases
- **MIT License**

### 3. Google ADK (Agent Development Kit)
**URL:** https://github.com/google/adk-python
- Code-first Python framework
- Model-agnostic (optimized for Gemini)
- Rich tool ecosystem (pre-built, OpenAPI, MCP)
- Agent Config (no-code agent definition)
- Tool confirmation flow (HITL)
- Modular multi-agent systems
- 260+ contributors
- **Apache 2.0**

### 4. Dapr Agents
**URL:** https://github.com/dapr/dapr-agents
- Built on Dapr for scalable autonomous systems
- Multiple agents reason, act, collaborate using LLMs
- Built-in observability, stateful workflows, resilience
- Kubernetes-native deployment
- **Latest: v1.0.0 (Mar 2026)**

### 5. AWS Agent Squad
**URL:** https://github.com/awslabs/agent-squad
- Multi-agent orchestration framework
- Intelligent intent classification
- Dual language: Python + TypeScript
- Universal deployment (AWS Lambda, local, any cloud)
- SupervisorAgent for coordinated teams
- **Latest: python_1.0.2**

### 6. OpenAI Agents SDK
**URL:** https://github.com/openai/openai-agents-python
- Lightweight, provider-agnostic
- 100+ LLM support (OpenAI + others)
- Guardrails, handoffs, human-in-the-loop
- Sessions, tracing, realtime agents
- Frequent updates, large contributor base
- **Latest: v0.13.x**

### 7. Solace Agent Mesh
**URL:** https://github.com/SolaceLabs/solace-agent-mesh
- Event-driven multi-agent systems
- Orchestrator agent for complex tasks
- REST, web UI, Slack interfaces
- Agent-to-agent communication via A2A Protocol
- Built on Solace AI Connector + Google ADK

### 8. MoltGrid
**URL:** https://github.com/D0NMEGA/MoltGrid
- Self-hosted REST API (FastAPI)
- Backend infrastructure for autonomous agents
- Memory (vector + key-value with tiered storage)
- Task queues with priorities, dead-letter, retry
- Inter-agent pub/sub messaging
- Cron scheduling, agent-to-agent escrow
- 208 endpoints across 34 services
- **Framework-agnostic** (works with LangChain, CrewAI, AutoGen)
- **Apache 2.0**

### 9. SuperAgentX
**URL:** https://github.com/superagentxai/superagentX
- 100+ LLM support
- 10,000+ MCP tools
- Browser automation (Playwright)
- Human-in-the-loop governance agent
- Persistent data store (SQLite/PostgreSQL)
- **Latest: v1.0.8 (Apr 2026)**
- **MIT License**

### 10. Mozilla Any-Agent
**URL:** https://github.com/mozilla-ai/any-agent
- Single interface to use and evaluate different frameworks
- Standardize how agents are built, run, compared
- Framework support expanding (contributions welcome)
- From Mozilla AI

---

## Multi-Agent Architecture Trends 2026

### Key Patterns

1. **Orchestrator-Worker:** Central coordinator delegates to specialized agents
2. **Three-Layer Hierarchical:** Governance → Execution → Compliance (OrgAgent pattern)
3. **Event-Driven Mesh:** Decoupled, async agent communication via message bus
4. **Agent Registry Pattern:** Cloud providers competing on governance/discovery layer

### Performance Reality (from recent studies)
- Multi-agent: **23% higher accuracy** vs single-agent
- Tradeoff: **15x more token consumption**
- Sequential reasoning: **39-70% degradation** in multi-agent
- Recommendation: Start single-agent, add more only when demonstrably needed

---

## Research Implications for Our AGI Project

### Priority 1: Integrated Agent Stack
Microsoft's journey shows the importance of unified tooling. Our integrated_agent.py combining ReAct + memory + planning + reflection + tools is aligned with industry direction.

### Priority 2: Agent Governance
The rise of Agent Registries as a battleground suggests we should build governance capabilities into our core framework:
- Agent registration/discovery
- Capability versioning
- Access control and audit trails

### Priority 3: Safety-First Self-Modification
Ouroboros pattern of multi-model review before code changes is becoming standard. Our existing self_analysis.py with review gates aligns with this.

### Priority 4: Tiered Context Management
With 15x token cost in multi-agent, efficient L0/L1/L2 loading is critical. Our tiered_memory.py implementation follows OpenViking's successful pattern.

---

## Research Questions

1. How will the shift from seat-based SaaS to outcome-based pricing affect agent architecture?
2. What governance patterns emerge when enterprises deploy agent fleets at scale?
3. Can we implement agent-to-agent escrow patterns similar to MoltGrid?
4. How should we structure a constitution/constitution.md for our agent's self-modification?

---

## Next Research Priorities

1. Deep dive into Microsoft Agent Framework 1.0 architecture patterns
2. Study Solace Agent Mesh event-driven patterns for our orchestrator
3. Analyze SuperAgentX governance agent implementation for safety patterns
4. Investigate Ouroboros constitution structure for self-modification guidelines

---

*Report compiled: 2026-04-13*
*Previous: 2026-04-12 - See AGENTS.md for complete build log*
