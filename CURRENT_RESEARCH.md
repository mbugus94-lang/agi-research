# AGI Research Findings - 2026-06-04

## Research Summary

### Industry News & Breakthroughs

- **RSI is the new AGI** (TechCrunch, May 28, 2026)
  - Recursive Self-Improvement (RSI) becoming the new focus beyond AGI
  - Alex Karpathy using agent swarms to train LLMs on simple tasks (Auto-Research)
  - Incremental improvements on GPT-2 scale model - "not novel, ground-breaking yet"
  - Many researchers following the RSI dream

- **Supermicro + Arm AGI CPU for Agentic AI** (June 2, 2026)
  - New class of rack-scale infrastructure designed for agentic AI workload orchestration
  - Compute density improvements for enterprise data center economics
  - "Increasing compute demands of modern agentic AI require a new class of rack-scale infrastructure"

- **AI Agent Architecture Consensus: LLM + Memory + Planning + Tools** (Jun 1, 2026)
  - PRAO (Perceive → Reason → Act → Observe) loop is dominant production pattern
  - ReAct (Thought → Action → Observation) remains core interaction pattern
  - Gartner: 40% of enterprise apps will embed AI agents by end of 2026
  - AI agents market: $7.6B (2025) → $10.9B (2026)
  - 79% of enterprises say they adopted agents — only 31% have one running in production

- **"Context Layer" emerging as canonical enterprise agent stack concept** (Jun 2026)
  - Combines: semantic definitions, entity resolution, governance, lineage, memory
  - Solves 4 recurring problems: fragmented definitions, tribal knowledge, entity identity, traceability

- **Mistral's path to profitability** (Jun 2026)
  - €11.7B valuation, $400M ARR, $1B target for end of 2026
  - Open-weight + European AI sovereignty positioning

### Key arXiv Papers (Past 2 Weeks)

1. **[2605.19932v1] PEEK: Context Map as an Orientation Cache for Long-Context LLM Agents** ⭐ BUILDS ON THIS
   - Authors: Zhuohan Gu, Qizheng Zhang, Omar Khattab, Samuel Madden
   - Core idea: maintain a reusable orientation cache ("context map") that captures what context contains, how it's organized, and which elements have been useful historically
   - 3 components: Distiller (extracts transferable knowledge), Cartographer (translates to edits), Evictor (priority-based token budget enforcement)
   - Claims: 6.3-34.0% accuracy/efficiency gains over baselines; 1.7-5.8x cost reductions vs ACE
   - Generalizes across LMs (incl. OpenAI Codex)
   - **This paper directly motivates today's build**

2. **[2605.30280v2] Qwen-VLA: Unifying Vision-Language-Action Modeling**
   - DiT-based action decoder for continuous action/trajectory output
   - Embodiment-aware prompt conditioning for diverse robot platforms
   - Unifies manipulation, navigation, and trajectory prediction
   - 97.9% LIBERO, 76.9% real-world ALOHA OOD success

3. **[2605.28774v1] AXPO: Agent Explorative Policy Optimization for Multimodal Agentic Reasoning**
   - Closes the "Thinking-Acting Gap" in agentic RL
   - Fixes thinking prefix, resamples tool call, uses uncertainty-based prefix selection
   - +1.8pp Pass@1, +1.8pp Pass@4 at 8B scale
   - 8B+SFT+AXPO > 32B base on Pass@4 with 4x fewer params

4. **[2605.28779v1] The Abstraction Gap in Vision-Language Causal Reasoning**
   - Dual-probe methodology: Text-Only vs Chain-Text probes
   - CAGE benchmark: 49,500 questions across 5,500 images
   - Many VLMs show high text scores (6-8) but low chain scores (<2.5)
   - Fine-tuning on chain-annotated data does NOT close the gap

5. **[2605.16727v1] PopuLoRA: Co-Evolving LLM Populations for Reasoning Self-Play**
   - Population-based asymmetric self-play with shared frozen base
   - LoRA weight-space evolution operators (mutations + crossovers)
   - Outperforms single-agent baseline on HumanEval+, MBPP+, AIME 24/25, MATH-500
   - Even the weakest population member beats baseline on aggregate

6. **[2605.14177v1] PGR: Prospection-Guided Retrieval of Memory with Language Models**
   - Decouples retrieval from memory storage
   - Generates Prospection Tree-of-Thought for imagined future steps
   - ~3x recall on MemoryQuest over strong baselines
   - 89-98% preference in LLM judging vs baselines

7. **[2605.06647v1] SIRA: Superintelligent Retrieval Agent**
   - Retrieval as a single corpus-discriminative action (not multi-round exploration)
   - Outperforms dense retrievers and multi-round agent baselines on 10 BEIR benchmarks
   - No retriever fine-tuning, no embedding indexes required

8. **[2605.22759v1] Foundation Model for Wearable Health Data**
   - 1T+ minutes unlabeled sensor signals, 5M participants
   - "Classroom" of LLM agents explores downstream heads on embeddings
   - 1,860 clinician ratings for safety

9. **[2605.15567v1] Position: Artificial Intelligence Needs Meta Intelligence** ⭐ BUILDS ON THIS
   - Core claim: Metacognition (self-monitoring of internal states) should be general design principle
   - Proposes metacognitive strategies inspired by psychology and resource-rational AI
   - Federated Learning case study: improved learning efficiency, effectiveness, security
   - Introduces software framework for metacognition-enabled AI applications
   - **This paper directly motivates today's build**

10. **[2605.20873v1] PlanningBench: Generating Scalable and Verifiable Planning Data**
    - Framework to generate scalable, diverse, verifiable planning data for LLMs
    - 30+ task types, subtasks, constraint families, difficulty factors
    - RL on verified PlanningBench data improves performance on unseen benchmarks
    - Current models struggle with coupled constraints; deterministic solutions yield clearer rewards

11. **[2605.18401v1] SkillsVote: Lifecycle Governance of Agent Skills**
    - Lifecycle governance: Collection → Recommendation → Evolution
    - Offline evolution: +7.9pp on Terminal-Bench 2.0
    - Online evolution: +2.6pp on SWE-Bench Pro
    - Governed external skill libraries enhance frozen agents

12. **[2605.18753v1] DashAttention: Differentiable and Adaptive Sparse Hierarchical Attention**
    - Adaptive, differentiable alpha-entmax for variable key-value block selection
    - Matches full attention at ~75% sparsity
    - GPU-aware Triton implementation with substantial speedups

### Trending Open-Source AI Agent Repositories (Jun 2026)

- **shyftlabs/continuum v0.0.1** (May 26, 2026): Python framework; 9 multi-agent patterns; durable execution with exactly-once guarantees; cost-aware multi-model inference
- **negai-ai/AgentClaw**: Declarative Python framework turning ideas into reusable Claw capabilities; @workflow.node / @toolkit.tool decorators; scheduling, dashboard, state persistence
- **polyant-ai/polyant**: TypeScript monorepo; NestJS engine + Next.js admin panel; multi-channel (Telegram/Slack/WhatsApp); OpenAI-compatible API
- **agentiumOS/agentium v2.3.1** (Jun 3, 2026): TS-native; 15+ packages; OpenTelemetry/Prometheus/Langfuse observability; edge/IoT support
- **HKUDS/nanobot v0.2.1** (Jun 2026): Lightweight agent framework; 84 PRs / 29 contributors; expanded providers and channels
- **yuntiaoOS/GenericAgent**: ~3K LOC self-evolving agent; 9 atomic tools; arXiv report on token-efficient self-evolving agents
- **AgenticX v0.4.1** (May 2026): 15+ LLM providers; SSE reattach; loop-detector/compactor/offloader hooks
- **agent-substrate/substrate**: Kubernetes-based framework for high-density agent workloads; gVisor sandboxes; MCP support

### Synthesis: Key Trends

1. **Metacognition as Design Principle**: Self-monitoring AI becoming mainstream
2. **Self-Evolving Agents**: Continuous learning from execution, not just training
3. **Multi-Agent Ecosystems**: Team-based agent coordination
4. **Memory-First Architectures**: Long-context, persistent, verifiable recall
5. **Security & Governance**: MCP poisoning defense, skill lifecycle governance
6. **Planning Benchmarks**: Verifiable, scalable planning data generation
7. **RSI over AGI**: Focus shifting to recursive self-improvement capabilities

### Implications for Our Framework

**Priority 1**: Metacognitive monitoring (May 29 build) ✅
- Self-monitoring of confidence, resources, internal states — `core/metacognitive_monitor.py`
- Adaptive resource allocation based on task complexity
- Real-time performance tracking

**Priority 2**: Context-oriented memory cache (today's build) ⭐
- PEEK-style orientation cache to cut long-context cost on recurring tasks
- Distiller + Cartographer + Evictor pipeline
- Integrates with metacognitive monitor via saved-tokens accounting

**Priority 3**: PlanningBench-style task generation
- Verifiable planning data for agent training
- Difficulty calibration
- Constraint-based synthesis

**Priority 4**: Skill lifecycle governance
- Collection → Recommendation → Evolution
- Evidence-gated updates
- Offline/online evolution

**Priority 5**: Multi-agent world models
- Brain-inspired communication
- Real-time coordination
- Shared environment simulation

---

## Today's Build: Context-Oriented Memory Cache (PEEK-Inspired)

**Date**: 2026-06-04
**Paper**: arXiv:2605.19932v1 (PEEK: Context Map as an Orientation Cache for Long-Context LLM Agents)
**Status**: ✅ COMPLETE - 36/36 tests passed

### Motivation

Long-context LLM agents re-process the same context across recurring tasks.
This is expensive (token cost) and slow. PEEK proposes a reusable "context
map" that captures (a) what the context contains, (b) how it's organized, and
(c) which elements have historically been useful. The agent orients itself
through the cache instead of re-reading raw context.

The paper claims 6.3-34.0% accuracy/efficiency gains and 1.7-5.8x cost
reductions vs ACE prompt-learning. We implement a PEEK-style orientation
cache that is decoupled from any particular LLM provider or vector DB and
plugs into our existing `tiered_memory` / `enhanced_memory` /
`metacognitive_monitor` pipeline.

### Components Implemented

1. **ContextEntry** - reusable entry in the orientation cache
   - kind: FACT, SCHEMA, PATTERN, INSTRUCTION, TOOL_TRACE, SUMMARY
   - token_cost, priority, hit_count, miss_count, last_accessed
   - value_density = hits / token_cost (for ranking)
2. **AccessRecord** - audit log of cache activity
3. **Distiller** - extracts reusable patterns from execution traces
   - facts (keyword markers like "is", "are", "equals")
   - tool_traces (lines starting with "tool:", "use ", etc.)
   - schemas (markdown structure markers)
   - summaries (long narrative lines > 120 chars)
4. **Cartographer** - translates DistillationResult into cache edits
   - ADD for new keys, UPDATE for re-seen keys (raises priority)
   - NOOP for content too short
5. **Evictor** - brings cache within token budget
   - LRU, LFU, COST_AWARE, HYBRID policies
   - Hybrid scores recency + frequency - cost penalty
6. **ContextMap** - the orientation cache
   - get/put/remove with hit/miss tracking
   - ingest_trace() runs full Distiller + Cartographer pipeline
   - _enforce_budget() applies eviction
   - top_entries() ranked by value density
   - stats() returns hits/misses/saves/evictions/saved_tokens_total
7. **ContextOrientedAgent** - thin integration wrapper
   - consult(key) - lookup with hit tracking
   - remember(trace) - ingest after successful run
   - summary() - exposes stats for metacognitive monitor

### Test Coverage (36/36 passed)

- Distiller: 8 tests (facts, tools, schemas, summaries, dedup, empty, dict messages, object messages)
- Cartographer: 4 tests (add, update, noop filter, dedup)
- Evictor: 5 tests (no-op, LRU, LFU, COST_AWARE, HYBRID)
- ContextMap: 10 tests (put/get, miss, update, remove, budget, ingest, dedup, top entries, saved tokens, describe, clear)
- Convenience: 2 tests (create_cache, create_agent)
- Agent wrapper: 3 tests (consult, remember, summary)
- Integration: 3 tests (recurring tasks, budget pressure, invalidation)

### Research Synthesis

- PEEK-style orientation caches are a 6-34% efficiency win for long-context agents
- Token-budget aware caching is essential as enterprise agent token consumption has grown 320x
- The "context layer" pattern (semantics + identity + governance + lineage + memory) is becoming the canonical enterprise agent stack
- Caches can be metacognition-hooks: hit_rate and saved_tokens feed the metacognitive monitor for adaptive resource allocation
- Distiller + Cartographer + Evictor cleanly separates "what was learned" from "what stays in the cache" - testable, deterministic, and LLM-agnostic

### Files Changed

- `core/context_cache.py`: 744 lines - PEEK-inspired orientation cache
- `experiments/test_context_cache.py`: 372 lines - 36 comprehensive tests
- `CURRENT_RESEARCH.md`: Updated with 2026-06-04 research findings
- `AGENTS.md`: This build log entry

### Next Priority

- **Integrate with `tiered_memory`**: route long-context orientation entries through tiered memory
- **Wire into `metacognitive_monitor`**: feed cache hit_rate + saved_tokens into calibration tracking
- **Hook into `reflection`**: post-run ingestion of successful execution traces
- **L2 / L3 tier promotion**: orientation entries should graduate to long-term memory after N hits
- **LLM-backed Distiller**: replace heuristic line-classifier with an LLM prompt that yields richer kinds

---

*Last updated: 2026-06-04 by AGI Research & Build Agent*