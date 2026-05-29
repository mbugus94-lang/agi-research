# AGI Research Findings - 2026-05-29

## Research Summary

### Industry News & Breakthroughs

- **RSI is the new AGI** (TechCrunch, May 28, 2026)
  - Recursive Self-Improvement (RSI) becoming the new focus beyond AGI
  - Alex Karpathy using agent swarms to train LLMs on simple tasks (Auto-Research)
  - Incremental improvements on GPT-2 scale model - "not novel, ground-breaking yet"
  - Many researchers following the RSI dream

- **DeepMind CEO Predicts AGI by 2030, Possibly 2029** (May 26-28, 2026)
  - Demis Hassabis at Google I/O 2026: "We're in the foothills of the singularity"
  - AI agents are a "practice run" for far more powerful systems
  - Society has only a few years to prepare
  - "Next-generation AI agents should be seen as a social stress test"

- **AI Could Make a Postgrad as Productive as a Lab** (May 26, 2026)
  - Hassabis: Single PhD student's output could match entire laboratory
  - "Free our PhD students, postdocs, to do higher-level work"
  - Science on brink of AI-driven discovery era

- **Fujitsu Self-Evolving Multi-AI Agent Technology** (May 25, 2026)
  - Multiple AI agents perform tasks as a team
  - Continuously learn from execution results, human feedback, policy changes
  - Can automate building business-specific LLMs

### Key arXiv Papers (Past 2 Weeks)

1. **[2605.15567v1] Position: Artificial Intelligence Needs Meta Intelligence** ⭐ BUILDS ON THIS
   - Core claim: Metacognition (self-monitoring of internal states) should be general design principle
   - Proposes metacognitive strategies inspired by psychology and resource-rational AI
   - Federated Learning case study: improved learning efficiency, effectiveness, security
   - Introduces software framework for metacognition-enabled AI applications
   - **This paper directly motivates today's build**

2. **[2605.20873v1] PlanningBench: Generating Scalable and Verifiable Planning Data**
   - Framework to generate scalable, diverse, verifiable planning data for LLMs
   - 30+ task types, subtasks, constraint families, difficulty factors
   - RL on verified PlanningBench data improves performance on unseen benchmarks
   - Current models struggle with coupled constraints; deterministic solutions yield clearer rewards

3. **[2605.18401v1] SkillsVote: Lifecycle Governance of Agent Skills**
   - Lifecycle governance: Collection → Recommendation → Evolution
   - Offline evolution: +7.9pp on Terminal-Bench 2.0
   - Online evolution: +2.6pp on SWE-Bench Pro
   - Governed external skill libraries enhance frozen agents

4. **[2605.18753v1] DashAttention: Differentiable and Adaptive Sparse Hierarchical Attention**
   - Adaptive, differentiable alpha-entmax for variable key-value block selection
   - Matches full attention at ~75% sparsity
   - GPU-aware Triton implementation with substantial speedups

5. **[2605.16551v1] PQR: Framework to Generate Diverse Queries Eliciting QA Agent Failures**
   - Iterative two-module system: query refinement + prompt refinement
   - 23-78% more unhelpful responses detected vs baselines
   - Targets specific agent objectives (helpfulness, safety)

6. **[2605.19064v1] Toward AI-Powered Computational Testbed for Workforce Policy**
   - LLM-powered generative agents for workforce simulation
   - Forecast cognitive, emotional, behavioral responses to organizational changes
   - Agents seeded with HR records, psychometrics, digital activity data

7. **Building Embodied EvoAgent: Brain-inspired Paradigm** (ACM Multimedia 2026)
   - Left-hemisphere: embodied context-augmented MLLM
   - Right-hemisphere: perceptual context-guided world model
   - Corpus callosum-style dynamic communication slots
   - Project: feliciaxyao.github.io/EvoAgent/

8. **OptiSMR: Unified Framework for Structured Reasoning and Self-Repairing MAS**
   - Multi-agent system for optimization modeling
   - 8.3% average improvement in solution accuracy
   - Handles LP, NLP, MIP, CO across 16 domains

9. **Functional Task Networks: Cortex-Inspired Spatial Parameter Isolation**
   - Binary mask over components for continual learning
   - No task ID required at inference
   - Reduces forgetting from +7.37 to +0.07 nats

10. **From Observed Reasoning to Stable Skills: Memory Substrate for Skill Graduation**
    - Cognitive Memory Manager (CMM) observes coding sessions
    - Extracts reasoning patterns as DAG
    - Curates recurring patterns into SKILL.md files
    - 61% reduction in assistant messages, 71% fewer files modified

### Trending Open-Source AI Agent Repositories (2026)

| Repository | Stars | Key Features |
|------------|-------|--------------|
| **oh-my-openagent** | 60K | 9 published packages, TypeScript, workspace architecture |
| **caveman** | 63K | Prompt compression, efficiency, cross-agent memory |
| **CowAgent** | 45K | Multi-model, multi-channel, memory + knowledge |
| **agent-zero** | 18K | Python framework, actively released |
| **Hermes Agent** | 15K | 22 messaging platforms, 808 commits in v0.14.0 |
| **paradigmxyz/centaur** | 462 | Self-hosted, Kubernetes sandbox |
| **elephant-agent** | 530 | Personal-model first, self-evolving |
| **quarqlabs/agent-oss** | 300+ | Memory-first, local, strict attribution |
| **nv-tlabs/Gamma-World** | New | Multi-agent world model, real-time rollout |
| **JuliusBrussee/caveman** | 63K | caveman-code, cavemem, cavekit ecosystem |

### Synthesis: Key Trends

1. **Metacognition as Design Principle**: Self-monitoring AI becoming mainstream
2. **Self-Evolving Agents**: Continuous learning from execution, not just training
3. **Multi-Agent Ecosystems**: Team-based agent coordination
4. **Memory-First Architectures**: Long-context, persistent, verifiable recall
5. **Security & Governance**: MCP poisoning defense, skill lifecycle governance
6. **Planning Benchmarks**: Verifiable, scalable planning data generation
7. **RSI over AGI**: Focus shifting to recursive self-improvement capabilities

### Implications for Our Framework

**Priority 1**: Metacognitive monitoring (today's build)
- Self-monitoring of confidence, resources, internal states
- Adaptive resource allocation based on task complexity
- Real-time performance tracking

**Priority 2**: PlanningBench-style task generation
- Verifiable planning data for agent training
- Difficulty calibration
- Constraint-based synthesis

**Priority 3**: Skill lifecycle governance
- Collection → Recommendation → Evolution
- Evidence-gated updates
- Offline/online evolution

**Priority 4**: Multi-agent world models
- Brain-inspired communication
- Real-time coordination
- Shared environment simulation

---

*Last updated: 2026-05-29 by AGI Research & Build Agent*
*Next update: Research synthesis and metacognitive monitoring integration*
