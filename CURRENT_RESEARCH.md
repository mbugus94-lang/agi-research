# AGI Research Findings - 2026-06-05

## Research Summary

### Industry News & Breakthroughs

- **NVIDIA Vera Rubin ramps into full production for "agentic AI factories"** (May 31, 2026, GTC Taipei)
  - 10x agent throughput at scale vs Grace Blackwell
  - Spectrum-X Ethernet Photonics in production - co-packaged optics for million-GPU AI factories
  - Rack-scale compute density push: Supermicro+Arm AGI CPU (Jun 2) and Spingence+Cooler Master follow the same playbook
  - Signal: the agent workload is large enough to anchor an entire hardware generation

- **Skift Data + AI Summit 2026: agent production-mode inflection point** (Jun 3, 2026)
  - Sierra: 95%+ of pilots reach production (vs MIT's 90% stuck in demo)
  - Evolve: guest-facing AI resolution went 30% → 60% in <120 days
  - Quote: "If you build an agent, you are accountable for what that agent does" - TUI / Amex GBT
  - Travel domain is the canary: integration with operational systems + accountability ownership

- **IBM Agentic Operating Model (Think 2026, May 30, 2026)**
  - Four pillars: agents + data + automation + hybrid
  - IBM Sovereign Core: governance embedded at infrastructure runtime level, not as app-layer config
  - Distinguishes IBM from hyperscaler competitors on operational sovereignty

- **NVIDIA GTC Taipei: Cooler Master + Spingence global "Digital Brain"** (Jun 4, 2026)
  - Closed-loop AI manufacturing: visual inspection agents + thermal simulation + digital twins + enterprise knowledge
  - Physical AI / Industrial agents integrate R&D, production, and simulation
  - Manufacturing becomes a multi-agent substrate, not a single-agent task

- **White House Executive Order: "Promoting Advanced AI Innovation and Security"** (Jun 2, 2026)
  - Treats frontier AI as critical operational infrastructure
  - Pushes data sovereignty + governance + procurement constraints into private sector
  - Agent builders will feel the compliance pull for the rest of 2026

- **Leiden Declaration on AI and Mathematics** (Jun 2, 2026)
  - 16 experts, 130+ signatories, endorsed by the International Mathematical Union
  - Concerns: reliability of AI-generated proofs, attribution, peer-review integrity
  - Reinforces theme of evidence-grounded reasoning: claims must carry their proofs

### Key arXiv / OpenReview Papers (Past 2 Weeks)

1. **CaveAgent: Transforming LLMs into Stateful Runtime Operators** (OpenReview p3dlOhpqKD) ⭐ BUILDS ON THIS
   - Dual-stream: semantic reasoning stream + persistent Python runtime stream
   - Persists DataFrames, DB connections, etc. across turns as runtime objects
   - Up to +13.5% on multi-turn retail (Tau²-bench), 28-51% token reduction
   - Open-source models reach 94.0-94.7% on BFCL, competitive with closed-source peers
   - **This paper directly motivates today's build**

2. **WISE: Long-Horizon Agent in Minecraft with Why-Which Reasoning** (OpenReview T8HuiP3yM9)
   - Causal Event Graph: explicit causal links between observations and task goals
   - Opportunistic Task Scheduler: re-prioritizes when causally relevant opportunities arise
   - Multi-scale progressive exploration: spatially comprehensive observation
   - Reinforces the "causal ledger" idea: durable memory of *why* an action helped

3. **Lexical Hints of Accuracy in LLM Reasoning Chains** (Sci Reports s41598-026-55000-2)
   - Words like "guess", "stuck", "hard" are the strongest predictors of incorrect answers
   - Intra-CoT sentiment volatility helps, but less so
   - CoT length only helps on intermediate-difficulty tasks
   - Reinforces value of post-hoc calibration signals over self-reported confidence

4. **Theory of Space: Active Spatial Belief Construction in Foundation Models** (OpenReview c2cxLvsdUp)
   - Active-Passive Gap: GPT-5.2 drops 57.1 → 46.0 when forced to gather information
   - Belief Inertia: false priors persist, especially in vision-based models
   - Identifies the bottleneck our evidence ledger is designed to surface

5. **SR-Scientist: Scientific Equation Discovery with Agentic AI** (OpenReview 5xwLFGdeWU)
   - Treats the LLM as an agent writing code, evaluating it, iterating
   - Outperforms baselines by 6-35% across four scientific disciplines
   - End-to-end RL over long-horizon tool use

6. **EvoMaster: Foundational Evolving Agent Framework for Agentic Science at Scale** (OpenReview lidiprht3N)
   - Self-evolving, trial-and-error learning in scientific inquiry
   - ~100 LOC to deploy capable self-evolving scientific agents
   - SOTA on Humanity's Last Exam (41.1%), MLE-Bench Lite (75.8%), BrowseComp (73.3%)

### Trending Open-Source Repos (multi-agent focus)

- **piotrwachowski/durable-agents** (alpha, June 2026): Python, Temporal-based durable execution, DeepAgents-style DX, sub-agent delegation, crash-proof resumable multi-agent
- **nemori-ai/langchain-dynamic-workflow** (v0.2.0, Jun 3 2026): Deterministic scripted multi-agent orchestration for LangChain deepagents, AST security gate, content-hash journal
- **LatticeAI v2.0.0** (TaeSooPark-PTS): Self-hosted Agentic Workspace Platform - Plugin SDK, Workflow Designer, Multi-Agent Runtime 2.0 (Planner/Executor/Reviewer/Researcher/Release)
- **voocel/agentcore v1.6.10**: Minimal composable Go library, work-stealing via IdleClaim, subagent nesting cap
- **agruai/multiagent-business-automation**: LangGraph + Neo4j + Qdrant + Redis multi-agent for business workflows with HITL approval gates
- **code-yeongyu/oh-my-openagent v4.6.0**: TypeScript multi-agent SWE framework, hardened prompt dispatch, Codex/LazyCodex install paths
- **zhayujie/CowAgent 2.1.0**: Multi-channel (Telegram/Discord/Slack/WeChat), i18n, streaming output, task cancellation
- **yaodub/cast**: Self-hosted multi-user multi-agent harness, design-driven agent builder, Claude integration

## Build Task: Causal Evidence Ledger (WISE + SciReports-inspired)

**Motivation**: Today's agent cycle makes claims and inferences, but has no substrate that records *which evidence* supports, refutes, or is missing for each claim. Research this week makes the case sharper than ever:

- **WISE** (Causal Event Graph): durable memory of why an action helped beats a stack of ungrounded text
- **CaveAgent**: stateful runtime objects are a substrate for verifiable feedback signals
- **Theory of Space**: foundation models suffer from belief inertia and ungrounded active inference
- **Lexical hints paper**: post-hoc calibration beats self-reported confidence as a grounding signal
- **Leiden Declaration**: the math community is asking for evidence-grounded AI claims, not vibes

The ledger closes the loop between the agent's reasoning (`Thought` stream), its tools (`Action`/`ExecutionResult`), and its reflection (`ReflectionEngine`). Reflection now has a substrate to call "this step's claim is ungrounded" or "this claim is refuted by tool output" instead of guessing.

### Key Components

1. **Claim** - proposition with author, tags, depends_on lineage, status, notes
2. **Evidence** - supports/refutes edge with kind (observation/tool_trace/memory/external/inference/user), weight, confidence, source
3. **ClaimStatus** - UNGROUNDED / SUPPORTED / CONTRADICTED / DISPUTED / EXPIRED
4. **EvidenceLedger** - substrate with assert_claim, add_support/add_refute, verify (single + bulk), lineage (DFS), descendants (BFS), related_evidence (lexical Jaccard), summary, calibration_signals
5. **verify()** - deterministic scoring: weighted_support vs weighted_refute with `weight × confidence` clipping; ties → DISPUTED, both-zero → UNGROUNDED, stale positives → EXPIRED
6. **calibration_signals()** - emits ungrounded_rate, contradiction_rate, disputed_rate, mean_confidence, expired_rate - feed directly into MetacognitiveMonitor

### Test Coverage: 33/33 tests passed ✅

- ClaimCRUD: 6 tests (assert, idempotent by id, tags/depends_on, remove drops evidence, remove unknown, all_claims)
- Evidence + verification: 8 tests (no-evidence, only support, only refute, mixed lead, disputed tie, confidence clip, remove, zero-weight)
- Freshness: 3 tests (fresh by default, expired after window, ungrounded becomes expired stale)
- Lineage: 5 tests (lineage ancestors, cycle-safe, descendants, related_evidence match, threshold filter)
- Summary: 4 tests (empty, counts each status, weakest, audit trail)
- Serialization: 3 tests (dict round trip, json round trip, audit cap)
- Calibration signals: 2 tests (empty, reflects state)
- Integration: 2 tests (full workflow, claim reuse with new evidence)

### Research Synthesis

- A causal evidence ledger is the substrate for *calibration*: signal > confidence
- Lineage + descendants + depends_on = causal graph that reflection and the metacognitive monitor can walk
- `calibration_signals()` is the bridge to `metacognitive_monitor`: ungrounded_rate feeds the calibration tracker
- The ledger is LLM-agnostic and deterministic - no behavior change, just data the other modules can consume
- The simplest "is this claim grounded?" check in the codebase is now `ledger.verify(claim_id).status`
- The stateful-runtime pattern from CaveAgent and the causal-graph pattern from WISE converge on a single substrate

### Files Changed

- `core/evidence_ledger.py`: 763 lines - new substrate
- `experiments/test_evidence_ledger.py`: 428 lines - 33 tests
- `core/__init__.py`: added public exports
- `CURRENT_RESEARCH.md`: this entry
- `AGENTS.md`: build log entry (next commit)

## Next Priority

- Wire `verify_trace` in `core/reflection.py` to consult the ledger and report evidence coverage per reasoning step
- Feed `calibration_signals()` into `MetacognitiveMonitor.assess_current_state()` as additional calibration input
- Bridge to `ContextMap`: convert SUPPORTED claims + their evidence into a single INSTRUCTION / SCHEMA entry (token-cheap verification memo)
- `BaseAgent` integration: expose `agent.ledger.assert_claim`, `add_support`, `add_refute`, `verify_all` from the cycle
- LLM-backed classifier for EvidenceKind: replace "user_statement" / "inference" heuristics with a small prompt

---

*Last updated: 2026-06-05 by AGI Research & Build Agent*