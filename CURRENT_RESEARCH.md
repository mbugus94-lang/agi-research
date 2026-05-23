# AGI Research Update - 2026-05-23

## Key Research Findings (Week of May 17-23, 2026)

### Industry News & Breakthroughs

**AI Agent Memory 2026 Benchmarks (Mem0)**:
- Single-pass ADD-only extraction now treats agent-generated facts as first-class
- Key challenges: temporal abstraction, cross-session memory evolution, privacy architectures
- Multi-scope memory pattern: user_id, agent_id, run_id, app_id tagging

**Multi-Agent AI Systems - Production Patterns**:
- Three dominant architectures now standard in production deployments:
  1. Hierarchical orchestration (manager + worker agents)
  2. Peer-to-peer collaboration (specialized agents negotiating)
  3. Market-based allocation (bid/ask for task assignment)

**Agentic AI Enterprise Adoption**:
- 91% of marketing teams now using AI agent tools
- 5 core agent patterns standardized: ReAct, Plan-Execute, Reflection, Multi-Agent, Tool-Augmented

---

### Key arXiv Papers (Past 2 Weeks)

#### 1. **[2605.14211v1] ASH: Agents that Self-Hone via Embodied Learning** ⭐ HIGH PRIORITY
**Link**: https://arxiv.org/abs/2605.14211v1

- **Core Idea**: Self-improving embodied agent learning from unlabeled, noisy internet video without reward shaping or expert demonstrations
- **Innovation**: Inverse Dynamics Model (IDM) trained from agent's own trajectories → extracts supervision from relevant internet video
- **Long-term memory**: Unsupervised identification and retention of key moments from large-scale video
- **Results**: 
  - Pokemon Emerald: 11.2/12 milestones (vs 6.0-6.5 baselines)
  - Zelda Minish Cap: 9.9/12 milestones
- **Relevance**: Scalable approach to long-horizon tasks via self-supervised IDM + retrieval-augmented memory
- **Action**: Implement self-honing loop in our framework

#### 2. **[2605.18401v1] SkillsVote: Lifecycle Governance of Agent Skills**
**Link**: https://arxiv.org/abs/2605.18401v1

- **Core Idea**: Governance framework for agent skills with lifecycle: Collection → Recommendation → Evolution
- **Skill definition**: Experience schema combining executable scripts with non-executable guidance
- **Offline evolution**: +7.9pp on Terminal-Bench 2.0
- **Online evolution**: +2.6pp on SWE-Bench Pro
- **Key insight**: Governed external skill libraries enhance frozen agents without parameter updates
- **Relevance**: Aligns with our skill acquisition module - add governance layer

#### 3. **[2605.16551v1] PQR: Framework to Elicit QA Agent Failures**
**Link**: https://arxiv.org/abs/2605.16551v1

- **Core Idea**: Generate diverse, realistic user queries that trigger agent failures
- **Components**: Query refinement module + Prompt refinement module
- **Result**: Uncovers 23-78% more unhelpful responses than prior methods
- **Relevance**: Add adversarial testing to our validation framework

#### 4. **[2605.15188v1] FutureSim: Replaying World Events to Evaluate Adaptive Agents**
**Link**: https://arxiv.org/abs/2605.15188v1

- **Core Idea**: Grounded simulation replaying real-world events chronologically
- **Benchmark**: Agents interact with Jan-Mar 2026 timeline, predict beyond knowledge cutoff
- **Results**: Top agent ~25% accuracy, many worse than no-prediction baseline
- **Relevance**: Test-time adaptation benchmark for long-horizon prediction

#### 5. **[2605.14498v1] GroupMemBench: Multi-Party Conversation Memory**
**Link**: https://arxiv.org/abs/2605.14498v1

- **Core Idea**: Benchmark for LLM agent memory in multi-party (not just dyadic) conversations
- **Challenge categories**: Multi-hop reasoning, knowledge updates, term ambiguity, temporal reasoning
- **Results**: Best systems ~46% accuracy; knowledge update only 27.1%
- **Relevance**: Our A2A protocol needs multi-party memory support

#### 6. **[2605.14968v1] GraphFlow: Formally Verifiable Visual Workflows**
**Link**: https://arxiv.org/abs/2605.14968v1

- **Core Idea**: Visual workflows as executable specifications with formal semantics
- **Compile-time**: Preconditions, postconditions, proof-checking
- **Runtime**: Append-only log, contract enforcement, replay/retries
- **Pilot**: 8,728 workflow runs, 97.08% completion across 3 clinical sites
- **Relevance**: Add formal verification to our workflow DAG module

---

### Trending Open Source AI Agent Repositories (May 2026)

| Repo | Stars | Language | Key Innovation |
|------|-------|----------|--------------|
| **HKUDS/nanobot** | 2.9k+ | Python | Ultra-lightweight core, MCP tools, chat channels |
| **bytedance/deer-flow** | 5k+ | Python | LangGraph-based, sandbox-aware, sub-agent spawning |
| **open-multi-agent/open-multi-agent** | 1.8k | TypeScript | Goal→DAG→parallelize→synthesize, 10 providers |
| **lsdefine/GenericAgent** | 11.9k | Python | ~3K lines, 9 atomic tools, cross-model support |
| **RightNow-AI/openfang** | 3k+ | Rust | Agent OS (not framework), 24/7 autonomous, 137k LOC |
| **ooropuloo/KohakuTerrarium** | 1.5k | Python | "Creatures" (self-contained agents), TUI + web UI |
| **aden-hive/hive** | 4.2k | Python | Production harness, graph-based DAG, crash recovery |
| **JuliusBrussee/caveman** | 2.1k | JavaScript | Token compression, ~2x fewer tokens than Codex |
| **HKUDS/OpenHarness** | 1.8k | Python | 43+ tools, ohmo personal agent, fork→code→test→PR |
| **agent0ai/agent-zero** | 8.5k | Python | Portable SKILL.md, Linux-in-a-box, extensible tools |

**Key Trends**:
1. **Lightweight cores**: GenericAgent (~3K lines), Nanobot (ultra-light)
2. **OS-level autonomy**: OpenFang (Agent OS), Agent Zero (Linux sandbox)
3. **Token efficiency**: Caveman aggressive compression
4. **Self-evolution**: GenericAgent, Ouroboros self-modification
5. **Production hardening**: Hive with crash recovery, GraphFlow verification
6. **MCP adoption**: Nanobot, multiple frameworks using Model Context Protocol

---

## Research Synthesis

### Emerging Design Patterns (May 2026)

1. **Self-Honing via IDM**: ASH shows learning from internet video via inverse dynamics models enables long-horizon improvement without expert demonstrations

2. **Governed Skill Libraries**: SkillsVote demonstrates that skill lifecycle governance (collection→recommendation→evolution) beats uncurated skill accumulation

3. **Formal Verification**: GraphFlow's compile-time proof-checking + runtime contract enforcement for mission-critical agent workflows

4. **Multi-Party Memory**: GroupMemBench reveals current memory systems fail at group conversations - need speaker-grounded belief tracking

5. **Embodied Video Learning**: ASH's approach to mining supervision from noisy internet video at scale

6. **Failure Elicitation**: PQR's adversarial query generation for finding agent weaknesses

### Priorities for Framework Development

1. **🔥 IMMEDIATE**: Self-honing loop (ASH-inspired) - learn from execution traces
2. **HIGH**: Skill governance layer - lifecycle management, voting, evolution
3. **HIGH**: Multi-party memory for A2A protocol
4. **MEDIUM**: Formal verification hooks for workflows
5. **MEDIUM**: Adversarial testing harness (PQR-style)
6. **LOW**: Video-based learning (requires infrastructure)

---

*Last Updated: 2026-05-23*
*Next Update: 2026-05-24*
