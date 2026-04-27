# AGI Research & Development Log

## 2026-04-27 - Latest Research Findings

### arXiv Papers (Past 2 Weeks)

#### [2604.07745v1] The Cartesian Cut in Agentic AI
- **Authors**: Tim Sainburg, Caleb Weinreb
- **Key Insight**: Examines "Cartesian agency" - the separation between learned core (LLM) and engineered runtime
- **Implication**: This split enables bootstrapping and governance but creates sensitivity bottlenecks
- **Relevance**: Provides framework for comparing agent architectures along autonomy/robustness/governance axes

#### [2604.04347v1] RoboPhD: Evolving Diverse Complex Agents Under Tight Evaluation Budgets
- **Key Innovation**: Elo tournament selection for agent evolution without separate validation split
- **Results**: Improved ARC-AGI from 27.8% to 65.8% using Gemini 3.1 Flash Lite
- **Method**: Self-instrumenting agents that generate diagnostic print statements for successors
- **Significance**: Demonstrates efficient evolution under budget constraints (1,500 evaluations)

#### [2603.13372] The ARC of Progress towards AGI: A Living Survey
- **Finding**: Performance degrades 2-3x from ARC-AGI-1 (~93%) to ARC-AGI-2 (~68.8%) to ARC-AGI-3 (~13%)
- **Cost Trend**: Test-time cost dropped ~390x in one year ($4,500/task → ~$12/task)
- **Insight**: Interactive learning and compositional reasoning remain unsolved challenges

#### [2604.18292] Agent-World: Scaling Real-World Environment Synthesis
- **Approach**: Self-evolving training arena with continuous lifelong learning
- **Results**: Agent-World-8B/14B models outperform proprietary baselines on 23 benchmarks
- **Key Concept**: Agentic Environment-Task Discovery autonomously probes databases/tools

#### [2604.15034] Autogenesis: A Self-Evolving Agent Protocol
- **Core Innovation**: Autogenesis Protocol (AGP) decouples evolution mechanics from execution
- **Components**: RSPL (resource substrate), SEPL (self-evolution), AGS (autogenesis system)
- **Availability**: Open source at DVampire/Autogenesis
- **Safety Feature**: Closed-loop operator interface with auditable lineage

#### [2604.15236] Agentic Microphysics: A Manifesto for Generative AI Safety
- **Key Concept**: "Agentic microphysics" - local interaction layer between agents
- **Methodology**: "Generative safety" - from micro-conditions to emergent risk analysis
- **Implication**: Safety must address population-level dynamics, not just individual models

### Trending Open Source Agent Repos (April 2026)

#### VoltAgent (VoltAgent/voltagent) - TypeScript Agent Platform
- **Stars**: Trending on GitHub, thousands of stars
- **Features**: Full framework + VoltOps Console for observability
- **Architecture**: Core runtime, workflow engine, supervisors/sub-agents, MCP integration
- **Key Capabilities**: Memory, RAG, guardrails, tool lifecycle, multi-provider LLM support
- **License**: MIT

#### DeerFlow 2.0 (bytedance/deer-flow)
- **Status**: Hit #1 GitHub Trending Feb 28, 2026
- **Focus**: Super agent framework with orchestration layer
- **Features**: Sub-agents, memory, sandboxes, extensible skills
- **Notable**: Complete rewrite from v1, integrates with Claude Code/Codex/Cursor/Windsurf

#### ClawAgents (x1jiang/clawagents_py)
- **Size**: ~2,500 LOC - lean and production-ready
- **Providers**: OpenAI GPT-5, Google Gemini, Anthropic Claude
- **Features**: Planning, memory, sandboxing, gateway server
- **Architecture**: Unified patterns from OpenClaw and DeepAgents

#### SuperAgentX (superagentxai/superagentx)
- **Scale**: 100+ LLMs, 10,000+ MCP tools
- **Focus**: Action-oriented agents with human-in-the-loop governance
- **Features**: Browser automation (Playwright), persistent state (SQLite/PostgreSQL)
- **Safety**: Human approval governance agent with auditability

#### AgentDock (AgentDock/AgentDock)
- **Focus**: Configurable determinism for reliable AI systems
- **Components**: Core backend + Next.js reference client
- **Notable**: Dr. Gregory House demo with multi-tool, multi-stage reasoning

#### KohakuTerrarium (DNLINYJ/KohakuTerrarium)
- **Concept**: "Creatures" (agents) in "Terrariums" (multi-agent networks)
- **Features**: Session persistence, scratchpad memory, multi-runtime (CLI/TUI/Web/Desktop)
- **Language**: Python-first with Vue/JS frontend

### Industry Insights (Datadog State of AI Engineering 2026)

- **Token Usage**: 69% of LLM input tokens are system prompts (scaffolding expansion)
- **Caching**: Only 28% of calls use cached context (massive inefficiency)
- **Failures**: Rate limit errors = 30% of all LLM call failures
- **Architecture**: 59% of agents are still monolithic (single call)
- **Framework Growth**: LLM framework adoption doubled year-over-year

### AGI Timeline Predictions

- **2026**: AGI timeline collapsed from 2060 to 2033 in just 6 years
- **2027**: ASI predicted by end of year (some forecasts)
- **2026 Q2**: ARC-AGI-3 released as new frontier benchmark
- **Hardware**: NVIDIA Vera Rubin with Groq dataflow coprocessor announced
- **Processors**: Arm's first AGI processor (Maia 200 chip) for agentic workloads

---

## 2026-04-25 - Previous Research

See BUILD_LOG_2026-04-24.md for complete history.

### Key Previous Builds
- **Tiered Memory System** (L0/L1/L2) - 75/75 tests passing
- **A2A Escrow Protocol** - 40/40 tests passing
- **Constitutional Governance** - 35/35 tests passing
- **MCP Tool Registry** - 27/27 tests passing
- **Verification & Attestation** - 42/42 tests passing

---

## Research Themes Identified

1. **Self-Evolution**: Multiple papers/protocols (Autogenesis, RoboPhD) focus on agents that improve themselves
2. **Multi-Agent Orchestration**: Trend toward supervisor/sub-agent patterns (VoltAgent, DeerFlow)
3. **Tiered Memory**: L0/L1/L2 context architectures gaining traction (OpenViking, industry adoption)
4. **MCP Standard**: Model Context Protocol becoming dominant for tool integration
5. **Verification-First**: Economics of AGI paper emphasizes verification bandwidth as bottleneck
6. **Governance**: Constitutional approaches (Ouroboros, Autogenesis) for safe self-modification
