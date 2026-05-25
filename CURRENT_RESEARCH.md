# AGI Research Update - 2026-05-25

## Key Research Findings

### Industry News & Breakthroughs

**Teams of AI Agents Boost Research Speed - Nature (May 2026)**
- Two new systems use teams of AI agents to develop hypotheses, propose experiments and analyze data
- Google DeepMind's Co-Scientist: Finds approved drugs for repurposing (leukaemia, liver fibrosis)
- FutureHouse's Robin: Found ripasudil as candidate treatment for dry age-related macular degeneration
- Quote: "It almost seems like an agentic, in silico implementation of the thought process in a scientist's head" - Vivek Natarajan, Google DeepMind
- Significance: AI agents moving from single-task tools to collaborative research teams

**Augury's Industrial AI Workforce (May 18, 2026)**
- Role-based AI agents collaborating with human factory workers
- Integration with Google Cloud and AVEVA for self-optimizing manufacturing
- Agents adapt to specific workflows rather than requiring workers to adapt to technology

**Dell Agentic AI Stack (May 18, 2026)**
- Token consumption for AI reasoning risen 320x
- Routing agent workloads to public cloud creates unsustainable costs
- Deskside Agentic AI for local execution to reduce latency and cost

**Agentic AI Foundation Growth (May 18, 2026)**
- 43 new members added (total 190 organizations)
- Open standard agentic AI stack development accelerating
- Enterprise and government adoption of open agent standards

### Key arXiv Papers (Past 2 Weeks)

1. **[2605.14211v1] ASH: Agents that Self-Hone via Embodied Learning** (Relevant to our self-honing module)
   - Self-improving agents learning from unlabeled internet video
   - Inverse Dynamics Model (IDM) trained from own trajectories
   - Results: 11.2/12 milestones vs 6.0-6.5 baselines in Pokemon/Zelda

2. **[2605.14212v1] MetaAgent-X: Breaking Ceiling of Automatic Multi-Agent Systems**
   - End-to-end RL framework for automatic multi-agent systems
   - Jointly designs AND executes agent workflows
   - ~21.7% gains over existing automatic MAS baselines
   - Key: Both designer and executor improve during training

3. **[2605.14163v1] Agentic Systems as Boosting Weak Reasoning Models**
   - Committee of weak models boosts reasoning through verifier-backed selection
   - GPT-5.4 nano: 67.0% single model → 76.4% with critic-comparator (k=8)
   - Oracle best-of-8 upper bound: 79.0%
   - Key insight: More agents expose latent correct solutions

4. **[2605.14392v1] Self-Evolving Reasoning via Verifiable Environment Synthesis**
   - EvoEnv: Model builds and refines its own training environments
   - Creates stable solve-verify asymmetry
   - Performance: 72.4 → 74.8 (3.3% relative gain)
   - Key: Sustainable self-improvement requires constructing worlds beyond current capability

5. **[2605.14324v1] Super-intelligence Survival Guide: Verification via Proof-Carrying Output**
   - Formal verification approach to AGI safety
   - Proof-carrying outputs to certify super-intelligent system decisions
   - IACR ePrint 2026/994

6. **[2605.14880v1] Building Embodied EvoAgent: Brain-inspired Paradigm**
   - Bridges multimodal LLMs with world models
   - Left-hemisphere: instruction understanding, visual interpretation
   - Right-hemisphere: spatial perception, environment dynamics
   - Corpus callosum communication via dynamic slots

### Trending Open-Source AI Agent Repositories

1. **google/adk-python v2.0.0** (GA Release)
   - Multi-Agent Workflow Engine: model-agnostic execution graphs
   - Dynamic Agent Collaboration: native inter-agent routing
   - Non-linear, conditional, cyclical agent execution
   - Parallel sub-agents, hierarchical teams, dynamic scheduling

2. **microsoft/agent-framework v1.6.0**
   - agent-framework-core: Shell tool for local/Docker execution
   - agent-framework-monty: CodeAct provider package
   - agent-framework-foundry: Hosted tool factories
   - agent-framework-a2a: Updated transport with immediate return

3. **paradigmxyz/centaur**
   - Self-hosted framework for shared AI agents (teams)
   - Slack-native agent conversations
   - Real execution in isolated Kubernetes sandboxes
   - 462 stars, 54 forks - active development

4. **craft-ai-agents/craft-agents-oss v0.9.5**
   - TypeScript framework for AI agents
   - 6K+ stars, UX polish for compact mode
   - MCP/branching stability improvements

5. **rayboto/easy-agent**
   - Terminal-native Claude Code-style agent
   - 31-phase roadmap for complete rebuild
   - Stage 21 complete: CLI, streaming, tool execution, sandboxing, sub-agents

6. **teodororo/trae-agent**
   - Multi-LLM support (OpenAI, Anthropic, Doubao, Azure, etc.)
   - Trajectory recording for debugging and analysis
   - Lakeview: concise summarization of agent steps

### Key Research Insights

1. **Multi-Agent Synergy > Single Agent**: MetaAgent-X and Weak Reasoning papers show coordinated agents significantly outperform single agents

2. **Verification is Critical**: Proof-carrying outputs and verifiable environment synthesis emerging as safety/quality mechanisms

3. **Self-Honing from Experience**: ASH demonstrates unsupervised learning from execution traces enables continuous improvement

4. **Brain-Inspired Architectures**: EvoAgent shows value of separating reasoning (LLM) from world modeling

5. **Environment Synthesis**: EvoEnv's approach of having agents construct their own training environments is a path to sustainable self-improvement

6. **Enterprise Agent Adoption**: 40% of enterprise apps will embed AI agents by end 2026 (Gartner prediction from recent research)

7. **Token Cost Crisis**: 320x increase in token consumption for reasoning - driving edge/local execution solutions

---

## Key Research Findings

### 1. Teams of AI Agents Transforming Scientific Research (Nature, May 2026)
Two groundbreaking multi-agent systems published in Nature:
- **Co-Scientist** (Google DeepMind): Multi-agent system for drug discovery and repurposing
  - Successfully identified treatments for leukemia and liver fibrosis
  - Uses hypothesis generation, experiment proposal, and data analysis agents
  - Represents "agentic, in silico implementation of scientist's thought process"
  
- **Robin** (FutureHouse): Drug discovery for dry age-related macular degeneration
  - Literature review agents → lab experiment selection agents
  - Identified ripasudil (glaucoma drug) as candidate treatment
  - Demonstrates specialized agents collaborating in scientific workflows

**Key Insight**: Domain-specific agent teams (hypothesis, experiment, analysis) collaborating through structured handoffs achieves scientific breakthroughs.

### 2. OpenAI Symphony: SPEC.md for Autonomous Coding Agent Orchestration
- Open-sourced specification for agent orchestration not tied to PRs
- Issues can instruct agents to analyze codebase and generate implementation plans
- Tree of tasks that Symphony schedules across multiple agents
- Enables autonomous code analysis → planning → execution workflows

**Key Insight**: Declarative task trees with dynamic scheduling across agent pools.

### 3. Dell Agentic AI Stack (May 18, 2026)
- Token consumption for AI reasoning has risen **320x**
- Cloud-only economics becoming unsustainable for continuous agentic workloads
- Dell Deskside Agentic AI series for local workstation deployment
- Liquid-cooled rack systems for data center scale

**Key Insight**: Edge/on-premise agent deployment becoming necessary due to cost scaling.

### 4. Agentic AI Foundation Growth
- 43 new members added (4 Gold, 27 Silver, 12 Associate)
- Total membership: **190 organizations**
- Building open standard agentic AI stack
- Interoperable, standardized agentic infrastructure focus

### 5. Google's Demis Hassabis on AGI (May 20, 2026)
- "It will be a profound moment for humanity" regarding AGI
- Testified about motivations for OpenAI founding (fears of Google/DeepMind AGI control)
- Google I/O 2026: Agent Platform strategy unveiled
- CodeMender integrated into broader agent ecosystem

---

## Key arXiv Papers (Past 2 Weeks)

### [2605.14211v1] ASH: Agents that Self-Hone via Embodied Learning
- Self-improving embodied AI learning from unlabeled internet video
- Inverse Dynamics Model (IDM) trained from own trajectories
- Unsupervised key moment identification from large-scale video
- Long-horizon tasks: Pokemon Emerald (~11.2/12 milestones), Zelda (~9.9/12)
- Scalable path to reducing reliance on labeled rewards/demonstrations

**Relevance**: Self-supervised improvement from execution traces - already implementing in self_honing.py

### [2605.15188v1] FutureSim: Replaying World Events to Evaluate Adaptive Agents
- Benchmark framework replaying real-world events chronologically
- Agents forecast beyond knowledge cutoff while interacting with live news stream
- Best agent: ~25% accuracy over 3-month horizon
- Many agents worse than no-prediction baseline

**Relevance**: Long-horizon adaptation, memory, search, uncertainty reasoning remain open challenges

### [2605.14968v1] GraphFlow: Formally Verifiable Visual Workflows for Agentic AI
- Workflow diagram as executable specification
- Compile-time: contracts (preconditions, postconditions) suitable for proof-checking
- Runtime: durable append-only event log, contract enforcement at boundaries
- Pilot: 8,728 runs, 97.08% completion

**Relevance**: Formal verification and auditability for mission-critical agent workflows

### [2605.18401v1] SkillsVote: Lifecycle Governance of Agent Skills
- Framework for skill governance: Collection → Recommendation → Evolution
- Skill profiling at scale (environment, quality, verifiability)
- Offline evolution: +7.9pp on Terminal-Bench 2.0
- Online evolution: +2.6pp on SWE-Bench Pro

**Relevance**: Governed skill libraries enhance frozen agents without model updates

### [2605.14498v1] GroupMemBench: Multi-Party Conversation Memory
- Evaluates memory in multi-party (vs dyadic) conversations
- Graph-grounded synthesis with per-user personas
- Leading systems: ~46% average accuracy, 27.1% knowledge update, 37.7% term ambiguity
- BM25 baseline often matches/surpasses memory systems

**Relevance**: Multi-user memory remains unsolved - current approaches miss group dynamics

### [2605.10114v1] SkillRAE: Agent Skill-Based Context Compilation
- Two-stage retrieval-augmented execution
- Multi-level skill graph (communities, skills, subunits)
- Skill-ranked retrieval with compact context compilation
- ~11.7% improvement on SkillsBench

**Relevance**: Context compilation as important as retrieval - skill graph organization

### [2605.16551v1] PQR: Generate Diverse Queries Eliciting QA Agent Failures
- Iterative two-module: query refinement + prompt refinement
- Uncovers 23-78% more unhelpful responses
- Produces more diverse, realistic failure-triggering queries

**Relevance**: Systematic failure discovery for QA agent evaluation

---

## Trending Open Source AI Agent Frameworks

### 1. google/adk-python v2.0.0 (20k stars)
- Production-grade toolkit for multi-agent workflows
- Flexible, model-agnostic execution graphs
- Non-linear and cyclical agent patterns
- Dynamic agent collaboration with inter-agent routing

### 2. microsoft/agent-framework v1.6.0
- agent-framework-core: shell tool for local/Docker
- agent-framework-monty: Monty-backed CodeAct provider
- agent-framework-foundry: hosted tool factories
- agent-framework-a2a: non-streaming transport

### 3. paradigmxyz/centaur
- Self-hosted AI agent framework for teams
- Slack-native conversations
- Isolated Kubernetes sandboxes per session
- Shared Python tool plugins
- Durable, auditable execution

### 4. enternovate/xavani-agent
- Fully local AI agent gateway
- Zero telemetry, no cloud dependency
- 169+ built-in skills across 27 categories
- Policy engine, protocol bridge, persistent memory
- MIT license, inspired by Hermes Agent

### 5. JuliusBrussee/caveman
- Token-efficiency focused: ~2x fewer tokens vs Codex
- caveman: output compression
- caveman-code: terminal coding agent
- cavemem, cavekit, cavegemma: memory/build/model tools
- 20+ providers, autopilot goal loop

### 6. niefa-xyz/niefa
- Neural Interference Engine for Agents
- Goal → planning → execution → self-correction
- Real-time visibility into decisions
- Safety controls: budget limits, sandboxed execution
- Next.js + TypeScript + FastAPI + LangChain

### 7. binzi1989/beeagi
- Enterprise-grade swarm orchestration
- Four-role swarm: Scout, Worker, Worm, Queen
- Scenario-driven workflows (Coding, Office, Research, Debug, Data, Product)
- Shadow replay evaluator for pre-production testing
- 5% canary allocator, auto-rollback governance
- Pheromone loop for task prioritization

---

## Research Synthesis

### Emerging Patterns (May 24, 2026)

1. **Multi-Agent Teams for Complex Tasks**: Nature papers show specialized agents (hypothesis, experiment, analysis) collaborating through structured workflows achieve breakthroughs impossible for single agents.

2. **Self-Honing from Execution**: ASH demonstrates unsupervised learning from trajectories enables sustained long-horizon progress without expert demonstrations.

3. **Formal Verification Becoming Critical**: GraphFlow shows 97% completion rates via compile-time contracts and runtime enforcement - necessary for production agent deployments.

4. **Skill Governance Lifecycle**: SkillsVote shows collection → recommendation → evolution pipeline improves frozen agents without retraining.

5. **Local/Edge Deployment Trend**: Dell's 320x token consumption increase driving on-premise agent infrastructure - cloud-only economics breaking down.

6. **Memory Remains Unsolved**: GroupMemBench shows leading systems only 46% on multi-party memory - humans excel at group dynamics, agents don't.

7. **Swarm Orchestration Emerging**: BeeAGI's four-role swarm, OpenAI Symphony's task trees, Google ADK's dynamic collaboration - multi-agent orchestration becoming standardized.

---

## Implications for Our Framework

### High Priority
- [ ] Integrate self-honing engine with skill crystallizer (convert patterns to skills)
- [ ] Implement formal verification hooks in workflow DAG (GraphFlow-style)
- [ ] Add multi-agent team support for specialized sub-agents
- [ ] Build skill governance lifecycle (collection → recommendation → evolution)

### Medium Priority
- [ ] Edge deployment optimization (local model inference)
- [ ] Multi-party memory improvements (group conversation tracking)
- [ ] Systematic failure discovery (PQR-style query generation)

### Research Questions
1. How to structure agent teams for scientific research workflows?
2. What verification contracts should workflow nodes enforce?
3. How to measure and improve multi-party memory accuracy?
4. Can we build a "pheromone" task prioritization system?

---

*Last Updated: 2026-05-24*
