# AGI Research Findings - 2026-06-06

## Research Summary (June 6, 2026)

### Industry News & Breakthroughs

- **Microsoft Build 2026 (May 19-22, 2026) — agentic app stack is now the platform story**
  - Foundry Agent Service + Rayfin (prompt→production backend) + Work IQ / Fabric IQ / Foundry IQ / Web IQ as a 4-IQ stack
  - Fabric IQ layers: Unified Data → Semantic Models → Ontologies; agents act on top
  - Direction: not "call an LLM", but "stand up an agent with knowledge, identity, and operational telemetry"
  - Implication: durable agent runtimes (the kind CaveAgent and EvoMaster push) move from research to first-class cloud concern

- **7-Layer Agentic AI Stack (AIMultiple, June 2026)**
  - Layers 1-7: Models → Agent runtime & infra → Orchestration → Memory/Knowledge → Tools & Actions → Observability/Eval → Agent Apps
  - Value concentration is uneven: the runtime + observability/eval tiers capture disproportionate economics
  - Implication for our repo: `core/evidence_ledger.py` and `core/trace_grounding.py` are the **observability/eval tier** of our own stack

- **Top 13 Agentic AI Trends (Firecrawl, 2026)**
  - 1M-token context windows (Claude Opus 4.6) feel like a solution but enable **poisoning**: hallucinations that get re-referenced across turns
  - Agents without fresh web data hallucinate **~35% more**
  - This is exactly the substrate problem the evidence ledger addresses: the ground truth for a claim is **external**, not in the context window

- **Failing Tools benchmark (OpenReview j7YsSnA64D)**
  - Even strong tool-use models drop to **<11.47% accuracy** when tools fail in 218 realistic scenarios
  - The failure mode is **missing verification or recovery steps**, not wrong tool choice
  - Direct echo of WISE / CaveAgent / our evidence-ledger work: the *check* step is the bottleneck

- **ACTS — Agentic Chain-of-Thought Steering (arXiv:2606.03965)**
  - Controller agent steers a frozen reasoner's step-by-step reasoning
  - Generates budgeted SFT steering trajectories that *guide the structure* of reasoning (plan / execute / check / conclude)
  - Direct alignment with our `TraceGrounder` step-type taxonomy and recommended-action vocabulary

- **ReNIO: Reweighting Negative Trajectory Importance (ACL ARR 2026)**
  - Improves on-policy distillation by reweighting negative trajectories more than positive
  - 8.9-10% relative gains on math/code; uses student-to-teacher probability ratio
  - Reinforces the calibration theme: the "what didn't work" signal is more informative than the "what did"

- **TEMPO: Timed Engagement with Memory and Persona Orchestration (ACL ARR 2026)**
  - System-1/System-2 dual-stream for long-horizon dialogue
  - NLI-based "stitching" drops a bridge word if it contradicts the System-2 sentence
  - Bounded Trait-State controller with mean-reverting Ornstein-Uhlenbeck updates
  - The stitching step is the same idea as the contradicted-step recommendation in our trace grounder

- **Model Interruption Bench (MIB, ACL ARR 2026)**
  - Full-duplex voice agents drop from 59-67% error detection (turn-based) to <10% true positives when interrupting mid-speech
  - Three behavioral archetypes: passive / post-hoc responder / aggressive
  - Reinforces the timing problem: metacognition is necessary but the action latency still dominates

- **GraP-Mem: Granularity-Aware Memory Planning (ACL ARR 2026)**
  - Plan Agent generates information needs; Integration Agent builds evidence state
  - When evidence is incomplete, expands access to source contexts
  - F1 / BLEU gains on LoCoMo and NarrativeQA across backbones
  - The "evidence state" idea is what `EvidenceLedger.evidence_for(claim_id)` produces

- **CuPS — Cultural Preference Signatures (Culture x AI 2026)**
  - Profile memories shift cultural reading styles in country-specific ways
  - Shifts occur even from *implicit* cues in pre-execution instruction documents
  - A new attack surface: a malicious memory item can steer agent behavior across claims

- **Diagnostic-Driven LLM Reward Design (OpenReview 5TmwBBn8Oh)**
  - DoorKey-8x8: 2.3% → 97.6% with diagnostic-driven iterative reward refinement
  - The taxonomy-driven prompt + targeted revision is the difference; random retries do nothing
  - Same lesson for our trace grounder: the **recommended_action vocabulary** matters more than the threshold tuning

- **SR-Scientist: Scientific Equation Discovery with Agentic AI (OpenReview 5xwLFGdeWU)**
  - 6-35% absolute gains over baselines across four scientific disciplines
  - End-to-end RL over long-horizon tool use
  - Reinforces the "agent writes + evaluates + iterates" loop

- **"The End of Software Engineering" (arXiv:2606.05608)**
  - "Agentic Engineering" is the emergent discipline: code is **ephemeral tooling for an LLM-driven reasoning loop**
  - Our repo lives at exactly this transition: code is the substrate, but the *agent's decisions* are the actual product

### Key arXiv / OpenReview Papers (Past 2 Weeks)

1. **ACTS (arXiv:2606.03965)** — controller agent steers a frozen reasoner's step-by-step plan / execute / check / conclude structure with budgeted thinking tokens
2. **Failing Tools (OpenReview j7YsSnA64D)** — recovery benchmark, <11.47% accuracy under failures, missing verification is the dominant failure mode
3. **TEMPO (OpenReview 918nhGBBc2)** — System-1/System-2 dialogue, NLI stitching, mean-reverting trait-state control
4. **GraP-Mem (OpenReview AUPI1ifc4v)** — granularity-aware memory planning, expands to source context when evidence is incomplete
5. **ReNIO (OpenReview kv6QSpUJbc)** — reweight negative trajectories for on-policy distillation
6. **Model Interruption Bench (OpenReview GPnWh7LbGm)** — interruption timing as the bottleneck for full-duplex agents
7. **Diagnostic-Driven Reward Design (OpenReview 5TmwBBn8Oh)** — taxonomy-driven iterative refinement vs random retries
8. **CuPS (OpenReview 1rvycjO0Ep)** — cultural preference signatures steered by profile memories
9. **SR-Scientist (OpenReview 5xwLFGdeWU)** — agent writes / evaluates / iterates on scientific equations
10. **End of Software Engineering (arXiv:2606.05608)** — agentic engineering as a new discipline

### Trending Open-Source Repos (multi-agent focus)

- **pewdiepie-archdaemon/odysseus** (56k+ stars, Jun 2026): Python/JS self-hosted LLM agent framework - local models (vLLM, llama.cpp, Ollama), Cookbok, Deep Research, Compare, Documents, Memory/Skills, multi-channel
- **code-yeongyu/oh-my-openagent v4.6.0** (61k stars, Jun 1 2026): TypeScript multi-agent SWE framework, hardened prompt dispatch
- **HKUDS/nanobot v0.2.1** (Jun 2026): real workbench agent, 84 PRs merged, 17 new contributors
- **selfonomy/duckagent v0.1.2**: Rust local-first runtime, 30+ LLM providers, 30+ channels (Telegram, Slack, Discord, Matrix, etc.)
- **aharonamir/GenericAgent**: minimal ~3K-line Python self-evolving framework, 9 atomic tools, browser control with session preservation
- **use-crux/crux** (May 2026): TypeScript toolkit for LLM orchestration with typed prompts / memory / retrieval / tools / guardrails / routing / evals / traces
- **Andree-9/ACTS** (arXiv:2606.03965-aligned): Agentic Chain-of-Thought Steering, budgeted thinking tokens
- **xinchen03/minta**: memory-focused self-correcting agent framework with hybrid retrieval
- **hognek/tinyagentos**: web desktop + agent OS, multi-framework (OpenClaw, Hermes, SmolAgents, Langroid, PocketFlow, OpenAI Agents SDK)

## Build Task: Trace Grounding Bridge (WISE + CaveAgent + ACTS-inspired)

**Motivation**: The 2026-06-05 build added a Causal Evidence Ledger as a substrate for evidence-grounded claims. Today's run wires that substrate to the agent's existing reasoning trace so reflection can ask "do we actually have evidence for each step we just took?" instead of guessing. The research case is unusually tight this week:

- **Failing Tools**: <11.47% accuracy under tool failure, dominated by *missing verification or recovery* — the *check* step is the bottleneck
- **ACTS**: the controller steers the reasoner's structure toward *plan / execute / check / conclude* — exactly the structure our grounder inspects
- **GraP-Mem**: "evidence state" is the right substrate for memory planning; we surface it as `EvidenceLedger.evidence_for(claim_id)`
- **TEMPO**: NLI-based stitching drops a bridge word if it contradicts the System-2 sentence — the contradicted-step recommendation in our grounder
- **Microsoft Build 2026**: agent observability/eval is the value-capture tier — our ledger + grounder is our tier-6 implementation
- **AIMultiple 7-layer stack**: observability/eval is one of the seven layers and disproportionate economics live there
- **Firecrawl 35% hallucination rate** when agents lack fresh data: external evidence, not context window size, is the ground truth

### Key Components

1. **TraceGrounder** - asserts one claim per step in the trace, attaches a piece of evidence, computes per-step verification, and produces a coverage report
2. **StepGrounding** - per-step evidence coverage dataclass: step_index, step_type, claim_id, verification, content_preview, plus full to_dict
3. **TraceGroundingReport** - aggregate report: coverage_rate, ungrounded / contradicted / disputed / expired step ids, weakest step ids, recommended_action
4. **Step type → evidence kind/polarity defaults** - explore/observe/search/execute/tool/code/verify/check/reflect/memory/user all map to the right EvidenceKind
5. **Status-aware polarity** - `output.status='error'` (or 'failed' / 'failure' / 'exception') takes priority over step-type default and adds REFUTES evidence
6. **Lineage via depends_on** - each step's claim depends on the previous step's claim, so reflection can walk the trace causally
7. **Stable ids** - `step:{trace_id}:{index}` and `trace:{trace_id}:{index}` so re-grounding the same trace reuses claims
8. **Recommended action vocabulary** - `none | reverify_ungrounded | reverify_contradicted | request_more_evidence | escalate_to_human | fallback_strategy` — all returned values are in the vocabulary
9. **Calibration blend** - `to_calibration_blend(report)` produces a small dict the metacognitive monitor can fold into its calibration signals
10. **Backward-compatible verify_trace** - `core/reflection.py:verify_trace(trace, output, ledger=None)` is fully backward compatible; when `ledger` is passed it surfaces `grounded`, `coverage_rate`, `recommended_action`, `contradicted_step_ids`, `weakest_step_ids`

### Test Coverage: 99/99 tests passed ✅

Trace grounding (55 tests):
- Construction & id stability: 5 tests
- Empty / minimal traces: 3 tests
- Happy path: 3 tests
- Contradicted steps: 4 tests
- Low coverage: 3 tests
- Step-type mapping: 10 tests
- Lineage: 2 tests
- Re-grounding: 2 tests
- Weakest step selection: 2 tests
- Recommended action vocabulary: 2 tests
- Serialization: 2 tests
- Calibration blend: 3 tests
- Ledger integration: 3 tests
- Trace independence: 2 tests
- Author attribution: 2 tests
- Performance: 1 test
- One-shot helper: 1 test
- Custom weight / confidence: 2 tests
- Content preview: 3 tests

Evidence ledger (33 tests, all still passing).

Reflection engine ↔ ledger integration (11 tests):
- Backward compatibility (no ledger) - 3 tests
- With ledger - 8 tests covering grounded flag, extra keys, action vocabulary, empty trace, incomplete trace, pure-claim growth, re-verify idempotence, and contradicted-step surfacing

### Research Synthesis

- The **observability/eval tier** (AIMultiple 7-layer stack) is where the economics live; our evidence-ledger + trace-grounding pair is the implementation
- The **Failing Tools** benchmark is empirical proof that the *check* step is the bottleneck; our grounder is the check
- The **ACTS** controller's plan / execute / check / conclude structure is exactly the structure we now verify after the fact
- **GraP-Mem's** "evidence state" idea is what `EvidenceLedger.evidence_for(claim_id)` returns in a single call
- **TEMPO's** NLI stitching is a runtime version of our contradicted-step recommendation
- The 35% hallucination rate from Firecrawl's analysis is the macro problem our 0.0%-of-context-window solution (external evidence) addresses
- Backward-compatible `verify_trace(ledger=None)` keeps the legacy path; agents that opt in to grounding get a richer return
- The recommended_action vocabulary is a small, LLM-agnostic protocol that any monitor or downstream consumer can branch on

### Files Changed

- `core/trace_grounding.py`: 491 lines - new bridge (TraceGrounder, StepGrounding, TraceGroundingReport, ground_trace, RECOMMENDED_ACTIONS, step-type → evidence-kind defaults)
- `core/reflection.py`: 321 → 364 lines - `verify_trace` extended with optional `ledger=` parameter that returns `grounded`, `coverage_rate`, `recommended_action`, `contradicted_step_ids`, `weakest_step_ids`
- `core/__init__.py`: added `TraceGrounder`, `TraceGroundingReport`, `StepGrounding`, `ground_trace` to public exports
- `experiments/test_trace_grounding.py`: 750 lines - 55 tests
- `experiments/test_reflection_ledger_integration.py`: 148 lines - 11 tests pinning the wiring between ReflectionEngine and EvidenceLedger
- `CURRENT_RESEARCH.md`: replaced with 2026-06-06 entry

## Next Priority

- Wire `verify_trace` into `BaseAgent`'s REFLECT step (so every cycle ends with an evidence-grounded self-check)
- Fold `to_calibration_blend(report)` into `MetacognitiveMonitor.assess_current_state()` as additional calibration input (closes the "signal > confidence" loop from the prior build)
- Add a `verify_all_traces()` helper to the ledger that grounds every trace in a session in one pass
- LLM-backed step classifier: replace the heuristic step-type → evidence-kind table with a small prompt for unknown step types
- Stress test: 100-step trace with 5 contradictory steps to confirm the grounder's throughput and weakest-selection
- Connect to `ContextMap`: convert SUPPORTED steps with their evidence into a single INSTRUCTION / SCHEMA entry (token-cheap verification memo)

---

*Last updated: 2026-06-06 by AGI Research & Build Agent*

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
  - Quote: "If you build a agent, you are accountable for what that agent does" - TUI / Amex GBT
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