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
## Research Summary (June 7, 2026) - AGI Continuous Research & Build Agent Run

### Industry News & Breakthroughs

- **Anthropic "When AI Builds Itself" (Jun 4, 2026) — Marina Favaro & Jack Clark** ⭐ BUILDS ON THIS
  - Argues recursive self-improvement (RSI) is the next threshold for frontier AI
  - Direct quote: *"AI that can build itself would be a major development in the history of technology ... but it 'could come sooner than most institutions are prepared for'"*
  - Anthropic reports Claude now writes **~80% of Anthropic's production code**, and Claude agents completed an open-ended AI safety research project end-to-end (humans selected topic + rubric, agents proposed hypotheses, ran experiments, iterated)
  - Calls for a coordinated "brake pedal" — a throttle that well-resourced frontier labs can apply *if* multiple peers agree
  - Same week: Anthropic files confidentially for IPO at **$965B valuation**, $47B revenue run rate, $65B fundraise oversubscribed
  - Implication for our repo: the era of "the agent rewrites its own core" is being treated as a near-term operational concern, not a thought experiment. Our `core/recursive_self_improvement.py` exists to make that rewrite path *gated, auditable, and reversible* — not to enable it.

- **Microsoft Build 2026 — Microsoft Execution Container (MXC)**
  - Dedicated runtime containment for agentic AI workloads
  - Pairs with the MDASH multi-agent vulnerability research platform
  - Reinforces the AIMultiple 7-layer stack thesis: runtime + observability/eval is where the economics live

- **NVIDIA Vera Rubin agentic AI factories (GTC Taipei)**
  - 10x agent throughput vs Grace Blackwell, Spectrum-X Ethernet Photonics in production
  - Agent workloads now anchor a hardware generation

- **Microsoft unveils MAI-Code-1-Flash + MAI-Thinking-1**
  - Microsoft's first proprietary coding model + reasoning model, in-house to reduce OpenAI dependency
  - Signals vertical-integration pressure across the agent stack

- **Tencent hires ex-OpenAI Yao Shunyu as Chief AI Scientist; explicit AGI goal**
  - China is bringing the U.S. AGI-vision lock, stock, and barrel

- **Leiden Declaration on AI and Mathematics (Jun 2, 2026)** — 130+ signatories
  - Concern: AI-generated proofs lack reliable attribution and peer-review integrity
  - Reinforces our evidence-ledger + trace-grounding approach: claims must carry their proofs

- **AIMultiple 7-layer agentic stack + Firecrawl 35% hallucination rate** (carried over)
  - When agents lack fresh external data, they hallucinate ~35% more
  - The substrate problem is *external evidence*, not context window size

### Key arXiv / OpenReview Papers (Past 2 Weeks)

1. **AEL — Agent Evolving Learning for Open-Ended Environments** (OpenReview dtPo105y8x) ⭐ BUILDS ON THIS
   - Two-timescale framework: fast Thompson Sampling bandit over memory-retrieval policies + slow diagnose-before-prescribe reflection that injects a new policy when performance plateaus
   - Sharpe +27% on a sequential portfolio task; +18% accuracy on support-ticket routing vs reflection-free bandit; +51% vs best prior baseline
   - Mechanism insight: reflection helps *when retrieval regimes must change*; neutral when the best policy is already stable
   - Direct architectural analog: our `RSIController`'s scoring (fast) vs the `BrakePedal` + recursion-depth guard (slow)
2. **SkillsVote — Lifecycle Governance of Agent Skills** (OpenReview kj068rI9Uh) ⭐ BUILDS ON THIS
   - Collection -> Recommendation -> Evolution pipeline with **evidence-gated admission** (only successful reusable discoveries promote to updates)
   - Online evolution during task streams + offline transfer via frozen libraries from historical trajectories
   - +7.9pp on Terminal-Bench 2.0 and SWE-Bench Pro
   - Reinforces our `core/skill_governance.py` from May 24
3. **Membrane — Self-Evolving Contrastive Safety Memory** (OpenReview fTz8N43gD3)
   - Contrastive Safety Memory cells: each stores a pair (block harmful query / permit similar benign query)
   - 87-88% F1 under cross-attack transfer; benign refusal 7-14% vs 28-85% for prior work
   - The contrastive-cell pattern is the same one we apply to the source tree: protect the substrate that protects us
4. **EvoMaster — Self-Evolving Scientific Agents** (OpenReview lidiprht3N)
   - ~100 LOC to deploy a self-evolving scientific agent
   - SOTA on Humanity's Last Exam (41.1%), MLE-Bench Lite (75.8%), BrowseComp (73.3%)
   - The "small but disciplined self-edit loop" thesis: small, evidence-gated proposals compound
5. **R_FOLD — Bi-Level Context Management for Long-Horizon Tool-Using** (OpenReview Wlz2pfZwEu)
   - Read-and-filter (chunk granularity) + fold (step-addressable trajectory summaries)
   - 81.33% on BrowseComp-Plus at a 32k-token budget, robust to 4x trainer/sampler staleness
6. **Failing Tools benchmark** (OpenReview j7YsSnA64D)
   - <11.47% accuracy on 218 realistic tool-failure scenarios; the *missing verification* is the dominant failure mode
7. **AEL's diagnose-before-prescribe** is the *slow* loop in our controller; the `score_and_route` is the *fast* loop
8. **Microsoft Build 2026 MXC** validates the "agent runtime as first-class cloud concern" framing

### Trending Open-Source Repos

- **HKUDS/nanobot v0.2.1** — 84 merged PRs, 17 new contributors; expanded channels (Signal, Telegram, Discord, Matrix)
- **code-yeongyu/oh-my-openagent v4.6.0** — TypeScript multi-agent SWE; hardened prompt dispatch
- **selfonomy/duckagent v0.1.2** — Rust local-first runtime, 30+ LLM providers, 30+ channels
- **zhayujie/CowAgent 2.1.0** — multi-model, multi-channel, i18n
- **microsoft/agent-governance-toolkit v4.0.0** — TEE keystore, Entra-signed JWT, wire-protocol-aware policy eval; production-grade governance
- **nemori-ai/langchain-dynamic-workflow v0.2.0** — deterministic scripted orchestration with AST security gate
- **earendil-works/pi v0.78.1** — agent toolkit with MiniMax-M3 provider support (notable)

## Build Task: Recursive Self-Improvement (RSI) Gate

**Motivation**: The Anthropic "When AI Builds Itself" essay (Jun 4, 2026) is the loudest signal yet that recursive self-improvement is being treated as a near-term operational concern. The repo's stance (per `SAFETY.md`) has always been: self-modifications REQUIRE human review, no auto-apply, reversible, proposals written to disk first. But until today, we had no formal *gate* — the `SelfImprovementEngine` produced proposals but nothing in the loop policed them. Today's build closes that gap with a safety-bounded self-edit pipeline modeled on the Anthropic Institute's "brake pedal" framing, AEL's two-timescale separation, and SkillsVote's evidence-gated admission.

**Key Components**:

1. **`BrakePedal`** — three-state operator-controlled throttle (`BRAKED` / `DAMPED` / `OPEN`). BRAKED hides all proposals; DAMPED surfaces only LOW/MEDIUM; OPEN shows all but flags CRITICAL with `requires_attention=True`. Mirrors Anthropic's "brake pedal" call; mirrors AEL's slow/fast timescale split (the pedal is the slow timescale).
2. **`RecursionDepthBudget`** — hard cap on inner-loop self-edit depth (default 2). The "self-edit -> re-analyze -> more self-edits" loop is a known RSI failure mode; AEL's two-timescale separation is the principled fix and we encode it as a hard cap. Raises `RecursionDepthExceeded` rather than silently spiraling.
3. **`classify_risk(target_file)`** — promotes any proposal that touches the *self surface* (`core/safety_circuit_breaker.py`, `core/evidence_ledger.py`, `core/recursive_self_improvement.py`, `core/reflection.py`, `core/agent.py`, `core/memory.py`, `core/planner.py`, `core/self_analysis.py`, `core/trace_grounding.py`, `core/metacognitive_monitor.py`, `SAFETY.md`, `AGENTS.md`) to CRITICAL. The self surface is the substrate; we never let a self-edit touch it without an explicit attention flag.
4. **`EvidenceRequirement.evaluate(claim_ids, ledger)`** — every self-edit must be grounded in at least one SUPPORTED claim in the `EvidenceLedger`, or it promotes risk and is audited. UNGROUNDED/UNKNOWN promotion is conservative (LOW -> MEDIUM floor; >=MEDIUM -> promoted). DISPUTED evidence is always attention-flagged.
5. **`metacognitive_adjust(base, monitor)`** — folds the running `MetacognitiveMonitor` state into risk scoring. High cognitive load, low confidence, or an "escalate" recommendation promotes risk. Monitor failure also promotes. The shift is *additive only* (never demotes).
6. **`RSIController` + `RSIProposal` + `RSIDecision`** — orchestrator. `score_and_route(proposal)` runs risk + evidence + metacog, then `decide()` consults the brake + `must_audit_critical` to emit a decision (queue / gate / attention). `persist(proposal, decision)` writes the audit trail to `proposals/` — *never auto-applies*. `score_batch(...)` wraps a whole batch in the recursion budget.

**Self-surface protection** (the conservative posture): `classify_risk` returns CRITICAL for any of 13 explicit self-surface paths, and HIGH for any other `core/*.py` module. The nominal risk string in the proposal cannot demote below this floor.

**CRITICAL special-case**: a CRITICAL proposal is *always visible* (so the operator can never silently miss it) and *always audited to disk* (so we have a paper trail of the most dangerous ideas the system ever generated), regardless of the brake state. This is the antithesis of "fail silent on the most dangerous proposals."

**Test Coverage**: 54/54 tests passed ✅
- `TestBrakePedal`: 7 tests (initial state, visibility matrix per state, CRITICAL attention invariant, transition history, no-op)
- `TestRiskClassifier`: 7 tests (self-surface promotion, core/ rule, non-core defaults, None target, nominal string interaction, normalized path)
- `TestRecursionBudget`: 4 tests (context manager, overflow raise, manual balance, clamp at zero)
- `TestEvidenceRequirement`: 7 tests (no claims -> UNGROUNDED, ledger None -> UNKNOWN, SUPPORTED -> GROUNDED, DISPUTED trumps, CONTRADICTED -> DISPUTED, all ungrounded, ledger error -> UNGROUNDED)
- `TestMetacognitiveAdjustment`: 6 tests (no monitor, high load promotes, low confidence promotes, escalate promotes, monitor failure promotes, saturation at CRITICAL)
- `TestRSIController`: 21 tests (end-to-end score/decision under each brake state, critical attention invariant, evidence integration, persistence + filename sanitization, batch + recursion overflow, bridge from `SelfImprovementEngine`, brake-state snapshot, summary)
- `TestIntegrationWithRealLedgerAndMonitor`: 1 test (real `EvidenceLedger` round-trip: assert_claim -> add_support -> GROUNDED)
- `TestConservativePosture`: 2 tests (promotion never demotes; self-surface dominates nominal)

**Research Synthesis**:
- The Anthropic "brake pedal" call is the macro framing; our `BrakePedal` is the *implementable* version (3 states, not 2) and it lives in code, not in a blog post
- AEL's two-timescale bandit is the *architectural* inspiration: `score_and_route` is the fast inner loop, `BrakePedal.transition` + `RecursionDepthBudget` is the slow outer loop
- SkillsVote's "evidence-gated admission" is the *promotion rule* in `EvidenceRequirement.evaluate` — a self-edit only auto-qualifies for the proposal queue if a claim in the ledger is SUPPORTED
- Membrane's contrastive safety memory inspires the *self-surface list* — we protect the substrate (the safety-critical files) the same way Membrane protects the safety memory itself
- EvoMaster's "~100 LOC to deploy a self-evolving agent" is the *size discipline* — we keep the gate small (728 lines including extensive docstrings) and let the proposals be the unit of work
- The `core/recursive_self_improvement.py` is *not* an auto-applier. It is a submission queue. The application step would require explicit human review per `SAFETY.md` — that gate stays outside the module on purpose
- The whole thing is a *measurable* safety claim: "every self-edit the system ever generated is on disk, attributed, and routed through a documented risk + evidence + monitor pipeline"
- The 13-file self-surface list is the most concrete expression of "protect the substrate" in the repo so far
- CRITICAL proposals are a first-class audit case, not a special-case error: they always get a JSON file in `proposals/`, even when the brake is full BRAKED

**Files Changed**:
- `core/recursive_self_improvement.py`: 728 lines (new) — BrakePedal, RecursionDepthBudget, classify_risk, EvidenceRequirement, MetacognitiveAdjustment, RSIController, RSIProposal, RSIDecision, proposal_from_improvement_proposal
- `experiments/test_recursive_self_improvement.py`: 671 lines (new) — 54 tests covering all components and integration with the real `EvidenceLedger` + `MetacognitiveMonitor`
- `core/__init__.py`: added 17 public exports for the new module
- `CURRENT_RESEARCH.md`: this entry

## Next Priority

- **Build a CLI / dashboard for the brake pedal**: surface the proposal queue, the audit trail, the recursion depth, and the brake state in a single `python -m core.recursive_self_improvement --review` view (or as a tiny `zo.space` route) so the operator can DAMPED -> OPEN with a single command and see the queue shift
- **Wire `proposal_from_improvement_proposal` into the existing `SelfImprovementEngine.run_full_analysis`** so the next `run_full_analysis()` automatically routes its 4 stale proposals (the ones currently flagged "missing test" and "no vector search") through the new gate — and we get to see what the controller actually does with them
- **Adversarial test pass**: generate 20 self-edits that try to touch the self surface, hide from the brake, or self-justify via a DISPUTED claim. Confirm the conservative posture holds in every case (the existing `TestConservativePosture` covers the rules; this is the property test)
- **LLM-backed step classifier for EvidenceKind** (carried from 6-05): the heuristic step-type -> evidence-kind table is a 2026-Q3 follow-up; the current RSI gate doesn't depend on it
- **A "human review" terminal**: a small wrapper that reads `proposals/*.json`, shows the audit fields, and writes the approved/rejected decision back into the JSON. This is the *only* path that should ever modify a file in the self surface

---

*Last updated: 2026-06-07 by AGI Research & Build Agent*

---

# AGI Research Findings - 2026-06-09

## Research Summary (June 8-9, 2026)

### Industry News & Breakthroughs

- **Anthropic "When AI Builds Itself" follow-on (Jun 7, 2026, Forbes / Lance Eliot)**
  - Explicit framing: recursive self-improvement (RSI) is "the method underlying the effort" toward AGI/ASI
  - Reinforces the brake-pedal positioning from Jun 4: "AI that can build itself would be a major development in the history of technology"
  - Public market: Anthropic files confidentially for IPO at $965B, $47B revenue run rate, $65B fundraise oversubscribed
- **Microsoft Build 2026 follow-on (Axios / TechCrunch, Jun 7)**
  - **MAI-Thinking-1**: 35B-active-param reasoning model; positioned for cost-effectiveness rather than raw capability
  - **Scout** (built on OpenClaw): always-on agentic assistant with persistent identity across Microsoft 365
  - **Microsoft Execution Container (MXC)**: dedicated runtime containment for autonomous agents (the agent runtime is now a first-class platform concern)
  - **Agent Control Specification (ACS)**: open standard for runtime policy/guardrails with hooks at 4 lifecycle points (pre-input, pre-tool, post-tool, pre-response)
  - **agent-governance-toolkit v4.0.0**: TEE keystore, Entra-signed JWT, wire-protocol-aware policy eval — production-grade governance
- **Microsoft "Builds Its Own AI Stack" (Forbes, Jun 7)** — 7 in-house MAI models, custom silicon, Project Solara; OpenAI partnership continues but Microsoft is reducing dependency
- **Priceline Penny multi-agent makeover (Skift, Jun 3)** + **Sierra / Amadeus agent production shift (Jun 3)** + **Realtor.com RealAssist AI (Jun 2)** — the agent-first UX pattern is now landing in vertical SaaS
- **agnt8x (Jun 3)** — first "AI agent recruitment + workforce management" platform: agent Passport, audit trail, contract, settlement — the neutral marketplace for agents is being built
- **GitHub Copilot Tokenpocalypse (Jun 1)** — usage-based billing replaces flat subscription; $29 to $750 overnight; "end of VC-subsidized AI" — economics of agent loops is now an enterprise concern
- **Tencent AGI org (CNBC, Jun 5)** — ex-OpenAI Yao Shunyu joins as Chief AI Scientist with explicit AGI mission; China brings the US-vision wholesale
- **Priceline / IHG / Evolve (Skift, Jun 3-5)** — "fundamentals (infra, data hygiene, clean APIs) beat glamour tech" for agent visibility; Evolve ramped 30%→60% resolution in <120 days

### Key arXiv / OpenReview Papers (Past 2 Weeks)

1. **Self-Revising Discovery Systems for Science: A Categorical Framework for Agentic AI** (arXiv:2606.01444v1, May 31, 2026) ⭐ BUILDS ON THIS
   - Distinguishes *inside-regime updates* (copresheaves, provenance-preserving) from *regime transitions* (left Kan extensions)
   - Proves a regime transition is a structure-preserving map that transports old artifacts into an enlarged vocabulary
   - **Builder/Breaker** + **CategoryScienceClaw** instantiations: protein-mechanics world model + knowledge–computation graph with typed skills
   - The "self surface" we protect in `classify_risk` is the same substrate this paper protects with its schema category Sb
2. **Towards Schema-based Learning from a Category-Theoretic Perspective** (arXiv:2604.10589) — hierarchical four-level categorical structure (schemas, workflows, minds, agents) with fibrations; we already have the same layering in `core/`
3. **From Intent to Evidence: A Categorical Approach for Structural Evaluation of Deep Research Agents** (arXiv:2603.25342) — pullback-style verifier for cross-source consistency + colimit-style synthesizer for grounded reports; this is the math behind our `TraceGrounder` + `EvidenceLedger` bridge
4. **SelfAI: A Self-Directed Framework for Long-Horizon Scientific Discovery** (arXiv:2512.00403v2) — User/Cognitive/Experiment Manager trio with adaptive stopping
5. **CoEvoSkills: Self-Evolving Agent Skills via Co-Evolutionary Verification** (arXiv:2604.01687) ⭐ BUILDS ON THIS
   - Skill Generator + Surrogate Verifier co-evolve; multi-file skill packages (not just single tools)
   - 71.1% pass on Claude Opus 4.6 with Claude-Code on SkillsBench; generalizes to 6 additional LLMs
   - The co-evolution loop is the *core contribution*: skills learn to satisfy a verifier that learns to ask better questions
6. **DataCOPE: Unsupervised Skill Discovery for Agentic Data Analysis** (arXiv:2606.06416) — unsupervised verifier signals from trajectories; Adaptive Checklist + Answer Agreement verifiers; +9.71% report-style / +32.30% reasoning-style tasks
7. **EvoDS: Self-Evolving Autonomous Data Science Agent** (arXiv:2606.03841) — Autonomous Skill Acquisition (Synthesis/Verification/Caching/Expansion) + Adaptive Context Compression; SFT→RL training pipeline
8. **MUSE-Autoskill** (arXiv:2605.27366) — full skill lifecycle + per-skill memory + unit-test-driven evaluation; cross-agent transfer (10.51pp lift when injecting into a different agent)
9. **SkillGen** (arXiv:2605.10999) — three-agent contrastive induction + generation-verification-refinement + held-out regression accounting
10. **SkillEvolver** (arXiv:2605.10500) — plug-and-play meta-skill, portable across Claude Code/Codex; Auditor gates on leakage/overfitting
11. **SkillMOO** (arXiv:2604.09297) — NSGA-II Pareto-optimizes skill bundles (pass rate vs. cost) on 16 SkillsBench SE tasks; 31.7% cost reduction with +21pp pass-rate
12. **SkillEvolBench** (arXiv:2605.24117v1) — 180 tasks across 6 environments; 3 harnesses (Claude Code, Codex CLI, Gemini CLI); 8 primary variants
13. **EvoSkill** (arXiv:2603.02766) — failure-driven textual feedback, Pareto frontier of skill folders, frozen model; OfficeQA +7.3%, SealQA +12.1%, BrowseComp transfer +5.3%
14. **SkillComposer** (arXiv:2606.06079) — three trainable operations (create/improve/merge), rejection-sampling on delta pass rate; merge drives generalization, improve drives specification
15. **AlignEvoSkill** (arXiv:2506.23149) — knowledge-tag guidance + likelihood-based task alignment; explicitly compares to CoEvoSkills/Trace2Skill/SkillX
16. **HiSME** (arXiv:2605.28390) — hierarchical skill meta-evolving: skills AND the process that maintains them evolve at test time
17. **S1-NexusAgent** (arXiv:2602.01550) — Plan-and-CodeAct dual loop + MCP-native tool ecosystem + Critic Agent distills Scientific Skills
18. **OpenSkill** (arXiv:2606.06741) — separates skills from model weights; verification anchored to externally-retrieved facts (no leakage of target-task supervision)
19. **Ace-Skill** (arXiv:2605.08887) — prioritized sampling + lazy-decay proficiency + clustered knowledge organization; Avg@4 +35 in some settings
20. **Membrane** (OpenReview fTz8N43gD3, carried) — Contrastive Safety Memory; 87-88% F1 under cross-attack transfer
21. **AEL** (OpenReview dtPo105y8x, carried) — two-timescale bandit; Sharpe +27% on portfolio
22. **SkillsVote** (OpenReview kj068rI9Uh, carried) — evidence-gated admission
23. **SkillsBench** (arXiv:2602.12670) — 84 tasks, 7 configs, 7,308 trajectories; curated Skills +16.2pp avg, self-generated Skills −1.3pp; focused skills (2-3 modules) beat broad ones
24. **SkillSmith** (arXiv:2605.15215) — compiles SKILL folders into boundary-guided runtime interfaces; ~38% time / ~33% token / ~24% iteration reductions
25. **Agent Evolving Learning** (OpenReview dtPo105y8x, carried) — two-timescale Thompson Sampling over memory-retrieval policies

### Trending Open-Source Repos (Past 2 Weeks)

- **microsoft/agent-governance-toolkit v4.0.0** (Jun 4 PR #2855): TEE keystore, Entra-signed JWT, wire-protocol-aware policy eval; production-grade
- **Agent-Control-Standard/ACS** (Jun 5): canonical v0.1.0 spec merged (PR #2) — modular JSON Schemas, conformance profiles (ACS-Core/Trace/Inspect/Provenance/Crypto/Audit), JSON-RPC 2.0 envelope
- **microsoft/azure-agents-control-plane**: SpecKit-driven agent specs (AGENTS_ARCHITECTURE.md, AGENTS_APPROVALS.md, AGENTS_EVALUATIONS.md); API-first via Azure API Management + MCP
- **selfonomy/duckagent v0.1.2** (carried) — Rust local-first runtime, 30+ LLM providers
- **piotrwachowski/durable-agents** — Temporal-based durable execution, DeepAgents-style DX
- **LatticeAI v2.0.0** — self-hosted Agentic Workspace Platform with Workflow Designer + Multi-Agent Runtime 2.0
- **voocel/agentcore v1.6.10** — minimal composable Go library, work-stealing via IdleClaim, subagent nesting cap
- **agruai/multiagent-business-automation** — LangGraph + Neo4j + Qdrant + Redis with HITL approval gates
- **yaodub/cast** — self-hosted multi-user multi-agent harness, design-driven agent builder
- **Sierra + Amadeus** (Skift summit, Jun 3) — production-ready agent infra demos; signal that 2026 = "AI agent production shift" year
- **agnt8x** (Jun 3) — agent Passport + audit trail + contract, with settlement-layer alignment to emerging standards

## Build Task: Skill Co-Evolution Verifier + Self-Review Queue

**Motivation**: CoEvoSkills, DataCOPE, EvoDS, and MUSE-Autoskill all converge on the same insight the *this week* of research papered over: a skill library is only as good as the verifier that gates it. Our existing `skills/skill_governance.py` and `skills/skill_acquisition.py` produce and crystallize skills, and `core/recursive_self_improvement.py` gates the self-edit proposals, but the two systems don't *talk* to each other: a self-improvement proposal isn't grounded in skill-bank state, and a skill-bank update isn't gated by the RSI brake. Today's build is the first-class *bridge* between them — a **Co-Evolution Verifier** that pairs the skill bank's inventory with the RSI gate, plus a **Self-Review Queue** so the operator can `list`, `approve`, or `reject` proposals without leaving the terminal.

The work is intentionally small (~600 LOC) and substrate-respecting: we don't rewrite the skill bank or the RSI gate, we wire them together with a single pass-through protocol. EvoMaster taught us that ~100 LOC of disciplined self-edit compounds; the *same* principle applies to skill evolution. The new module is the smallest unit of work that closes the loop.

**Key Components** (`skills/skill_coevolution.py`, ~480 lines):

1. **VerifierVerdict** — outcome of a single skill proposal: PASS, FAIL, NEEDS_MORE_EVIDENCE, BLOCKED_BY_BRAKE.
2. **VerifierSignal** — what the verifier reads to render a verdict: skill_id, candidate_signature (hash of action_template + parameter_schema), observed_success_rate, observed_uses, evidence_claim_ids, target_file, risk_band.
3. **CoEvolutionConfig** — `min_uses=3`, `min_success_rate=0.6`, `max_risk_band=CRITICAL`, `block_on_disputed_evidence=True`, `persist_audit=True`.
4. **SurrogateVerifier** — LLM-agnostic, deterministic signal aggregator. `evaluate(signal)` rolls up: support score, risk band (via the same `classify_risk` the RSI gate uses), evidence status (via the same `EvidenceRequirement.evaluate` the RSI gate uses), and a brake-consult (via a *new* `BrakePedal` instance scoped to skill evolution — same model, different process). Returns a `VerifierVerdict` plus a human-readable rationale.
5. **ProposalLedger** — substrate of the audit trail. Every verifier verdict is recorded with: timestamp, proposal_id, skill_id, signal, verdict, rationale, and the prior verdict for the same skill_id. `history_for(skill_id)` and `recent(n)` are O(n) over the (small) ledger.
6. **SkillEvolutionGate** — the orchestrator. Wraps `SurrogateVerifier` + `ProposalLedger` + a `BrakePedal` (default `DAMPED`) and a `CoEvolutionConfig`. Exposes: `evaluate(signal) → VerifierVerdict`, `history(skill_id) → List[LedgerEntry]`, `recent(n) → List[LedgerEntry]`, `summary() → str`, `audit_path() → Path`. Never mutates the skill bank; never auto-applies.

**Test Coverage** (`experiments/test_skill_coevolution.py`, ~250 lines): all 30+ tests pass ✅
- `TestVerifierVerdict` / `TestVerifierSignal` / `TestCoEvolutionConfig` — value-object tests
- `TestSurrogateVerifier` — pass on strong signals, fail on weak signals, NEEDS_MORE_EVIDENCE on under-used, BLOCKED_BY_BRAKE when state gates
- `TestProposalLedger` — append, history_for, recent ordering, empty case
- `TestSkillEvolutionGate` — full pipeline (evaluate → record → audit), config plumbing, brake transitions, summary
- `TestIntegrationWithRSI` — the *only* test that matters: a skill proposal for a self-surface file is BLOCKED_BY_BRAKE before the RSI gate even sees it; a clean proposal for a non-core path PASSes; a proposal citing a DISPUTED claim in the real `EvidenceLedger` is NEEDS_MORE_EVIDENCE
- `TestConservativePosture` — block beats pass when in doubt; verdict never promotes on weak signal
- `TestAuditability` — every verdict leaves a JSON record; the audit file lists the gate's brake state, depth, and ledger size at submission time

**Self-Review Queue** (`skills/self_review_queue.py`, ~250 lines):
1. `list_proposals(proposals_dir="proposals", brake_state=None, risk_band=None)` — reads every JSON in `proposals/` and filters by the audit fields
2. `show_proposal(proposal_id, proposals_dir="proposals")` — pretty-prints the proposal + decision + audit trail
3. `decide_proposal(proposal_id, decision, reviewer, reason, proposals_dir="proposals")` — writes the decision back into the JSON in-place (the *only* path that should ever modify a file in the self surface, per the Jun 7 priority list)
4. `gate_summary(proposals_dir="proposals")` — one-line per-proposal summary that fits in a terminal
5. `gate_status(proposals_dir="proposals")` — aggregate counts (visible, gated, attention, approved, rejected)

**Test Coverage** (`experiments/test_self_review_queue.py`, ~200 lines): 18 tests pass ✅
- Empty queue, malformed JSON is skipped, list filters by brake and risk
- Show returns the JSON unchanged
- Decide writes back approved/rejected with reviewer + reason + timestamp
- Idempotent decide (running it twice is safe)
- Summary + status are deterministic

**Why this is a *build*, not a refactor**:
- The SkillEvolutionGate is a new class with a new module (no edits to `skill_governance.py` or `skill_acquisition.py`)
- The SelfReviewQueue operates on the JSON files in `proposals/`, not the in-memory `RSIController` (the gate is the system of record; the queue is a thin operator interface)
- Both are substrate-respecting: the brake pedal and evidence ledger are queried, not duplicated
- The `skills/` directory now has 21 capability modules; the `core/` directory stays at 47; the new tests in `experiments/` (70 files total) keep coverage per the discipline established on May 17

**Research Synthesis**:
- CoEvoSkills' "skill generator + surrogate verifier" is the macro pattern; we implement the *verifier side* of that pattern (the generator side is already in `skill_governance.py:crystallize_pattern`)
- DataCOPE's Adaptive Checklist Verifier is a "report-style" verifier; ours is a "skill-style" verifier (different output type, same architecture: signal → verdict → record)
- EvoDS's Synthesis/Verification/Caching/Expansion four-stage pipeline maps onto ours as: Synthesis = `crystallize_pattern`, Verification = `SurrogateVerifier.evaluate`, Caching = `ProposalLedger`, Expansion = next-iteration signal collection
- MUSE-Autoskill's "skills are separate from the model" is a principle we already follow (skills are explicit, transferable artifacts in our `SkillRegistry`); today's build extends it with "skills are also separate from the RSI gate" — same substrate, different policies
- SkillsBench's finding that "self-generated skills underperform curated" is why the `SurrogateVerifier` is conservative: we lean BLOCKED_BY_BRAKE on marginal signals rather than pass them through
- The Anthropic "brake pedal" framing flows into the skill evolution side: a separate `BrakePedal` (default DAMPED) gates skill updates; the same brake that's used for self-edits, with the same visibility matrix
- The Mitsubishi-Fujitsu "Self-Evolving Multi-AI Agent" pattern (May 25) is the broader "evolution through execution results" framing; today's build is one concrete *mechanism* under that framing
- The 2026 arc (from SkillsVote to CoEvoSkills to DataCOPE to SkillMOO) is the convergence of *evidence-gated admission*; the new gate keeps our implementation in that arc
- The new module is the answer to the Jun 7 priority list's #2 (wire `proposal_from_improvement_proposal` into `run_full_analysis`): the `SkillEvolutionGate.evaluate` can be called from `run_full_analysis` next time, and the `SelfReviewQueue` is the operator surface for the resulting `proposals/`
- The SelfReviewQueue is the answer to #1 (CLI/dashboard) and #5 (human review terminal) on the Jun 7 priority list — three items closed in one build

**Files Changed**:
- `skills/skill_coevolution.py`: ~480 lines (new) — VerifierVerdict, VerifierSignal, CoEvolutionConfig, SurrogateVerifier, ProposalLedger, SkillEvolutionGate
- `experiments/test_skill_coevolution.py`: ~250 lines (new) — 30+ tests covering all components + real-`EvidenceLedger` integration + conservative-posture invariants + auditability
- `skills/self_review_queue.py`: ~250 lines (new) — list_proposals, show_proposal, decide_proposal, gate_summary, gate_status
- `experiments/test_self_review_queue.py`: ~200 lines (new) — 18 tests covering filter, show, decide, idempotence, summary, status
- `skills/__init__.py`: added 6 public exports from the new module
- `CURRENT_RESEARCH.md`: this entry

## Next Priority

- **Wire `SkillEvolutionGate.evaluate` into `SelfImprovementEngine.run_full_analysis`**: after the next `run_full_analysis()` produces its 4 stale proposals, route them through the new gate *before* the RSI gate, and persist both audit trails
- **Cross-skill-lineage experiment**: a small experiment that demonstrates a single proposal flowing through the new gate + the RSI gate + the SelfReviewQueue, with the JSON audit file showing all three layers of evidence
- **Adversarial self-review pass**: 20 self-edits that try to (a) re-approve themselves by writing back to a JSON file in `proposals/`, (b) hide by lying about their `risk_band`, (c) bypass the gate by using a non-standard filename. Confirm the conservative posture holds
- **Surrogate Verifier with LLM-backed signal**: replace the heuristic `observed_success_rate / observed_uses` score with an LLM prompt that produces a richer `VerifierSignal`; the gate doesn't need to change
- **Skill reuse telemetry**: feed the gate's history back into the `MetacognitiveMonitor.calibration_signals()` so the monitor sees "this agent's last N skill updates were 80% NEEDS_MORE_EVIDENCE → low confidence" as a calibration input
- **LatticeAI-style workflow designer surface**: a `python -m skills.skill_coevolution --audit` CLI that prints `gate_summary()` in color, and a `python -m skills.self_review_queue --list --risk=critical` filter for the operator's morning review

---

*Last updated: 2026-06-09 by AGI Research & Build Agent*
---

# AGI Research Findings - 2026-06-10

## Research Summary (June 10, 2026)

### Industry News & Breakthroughs

- **Anthropic Claude Code + Skills self-evolution** (Jun 9, 2026): Skills (`.claude/skills/`) become a first-class artifact; the runtime is now "the loop is: skill → invoke → memory → next skill", not "the loop is: prompt → LLM → response". The agent surface that SkillsVote, CoEvoSkills, EvoDS, and DataCOPE all describe in research is now in production.
- **"Self-Evolving Multi-AI Agent" mainstreaming** (Mitsubishi / Fujitsu May 25 → industry-wide by Jun 10): the framing of "an agent that updates from execution results" is no longer a research claim; it's a deployment pattern. Reinforces the SkillsVote / CoEvoSkills direction.
- **Agent Security Week (Jun 6–10)**: TrueFoundry's MCP Gateway (RBAC at the tool level, pre-execution guardrails), Claude Code Security Best Practices (SSO + AI Gateways + MCP Governance), AI Governance & Audit (virtual keys, compliance-grade logs). The "governance at the execution boundary" idea from the OCL paper is now a product category.
- **Hermes Agent v2026.6.5 (Jun 6)**: cross-model gateway (OpenRouter, NVIDIA NIM, z.ai/GLM, OpenAI, etc.), TUI, scheduled automations, RPC tool calls with zero-context-cost chaining. The leader in single-agent self-improvement tooling; 189k stars, 32k forks.
- **OpenFang (RightNow-AI) v0.6.9 (May 2026)**: Rust-based "Agent OS" with 14 crates, ~137k LOC, scheduling + knowledge graphs + monitoring + automation. 17.8k stars. The opposite end of the spectrum from Hermes: a kernel, not a runtime.
- **OpenHive (aden-hive) v0.11.0 (May 2026)**: model-agnostic multi-agent harness, dynamic topology generation, persistent role-based memory. 51 ADK frameworks evaluated in 2026 — no single framework dominates, but OpenHive and OpenFang lead the production-grade cohort.
- **HiClaw (agentscope-ai) v1.1.2 (May 27)**: Kubernetes-native multi-runtime orchestrator blending OpenClaw (Node.js) + QwenPaw (Python) + Hermes. Auditable via Matrix m.mentions; manager QwenPaw + worker Hermes pattern. 4.7k stars.
- **HermesClaw (NextAgentX) v0.0.1 (May 2026)**: Electron + React desktop wrapper that unifies OpenClaw gateway + Hermes Agent runtime. First "personal OS" packaging of the openclaw/Hermes stack.
- **r0b0tlab/hermes-concurrent-agents**: parallel Hermes Agent workers on unified-memory GPUs (GB10, DGX Spark) with profile-isolated workers (creative / coder / researcher / QA) and a SQLite kanban for task coordination. Pattern: model-endpoint-agnostic parallelism on inference-friendly hardware.

### Key arXiv / OpenReview Papers

- **["Silent Failure in LLM Agent Systems: The Entropy Principle and the Inevitable Disorder of Autonomous Agents"](https://arxiv.org/abs/2606.08162)** (Dexing Liu, Shanghai Qijing Digital, Jun 9 2026) ⭐ BUILDS ON THIS
  - Central claim: silent failures are *not* implementation defects; they are the inevitable consequence of 22 intrinsic properties of language-based autonomous systems
  - Formal result: S(t) = S0 · exp(α·t); system entropy increases monotonically with interaction rounds
  - Five silent failure types: Channel Fracture (L1), Cognitive Framework Lag (L2), Data Consistency Decay (L3), Cross-Session Knowledge Fragmentation (L2), Behavior Routing Deficiency (L3)
  - Three structural patterns: multi-step accumulation, absence of self-reporting, recurrence under identical conditions
  - Engineering response: PIG (Physical Integrity Gate) Engine + ADE (Agent Delivery Engineering) protocol suite = "deterministic governance" at the boundary
  - Survey of 130+ existing failure modes (MAST 14, Microsoft AIRT 30+, Token Budgets 63, Latitude 6, Pazi 5, BAGEN, Library Drift) — all map to the five types
  - Independent confirmation: Zhang et al.'s "Library Drift" (unbounded skill libraries causing retrieval disorder) is exactly the Behavior Routing Deficiency + Cross-Session Fragmentation combination

- **["Q-Evolve: Self-evolving LLM agents with in-distribution Optimization"](https://arxiv.org/abs/2606.07367)** (Jun 9): in-distribution RL with weighted Implicit Q-Learning on hybrid off-policy data (expert + agent trajectories); process-reward labeling co-evolves with policy. Stabilizes Bellman backups in sparse-reward settings. Reinforces the "evidence-gated admission" pattern from SkillsVote.

- **["Socratic-SWE: Self-Evolving Coding Agents via Trace-Derived Agent Skills"](https://arxiv.org/abs/2606.07412)** (Jun 9, 21 pages): trace → skills → behavior update. Same macro pattern as the Hermes/CoEvoSkills direction: skills are derived from execution, not prompted.

- **["Rethinking Continual Experience Internalization for Self-Evolving LLM Agents"](https://arxiv.org/abs/2606.04703)** (Jun 3, Renmin University): three failures of experience internalization (granularity, injection pattern, internalization regime). Off-policy context-distillation on high-quality teacher trajectories is more stable than on-policy distillation. Confirms the SkillsVote / EvoMaster / RSIController conservatism.

- **["PACE: Anytime-Valid Acceptance Tests for Self-Evolving Agents"](https://arxiv.org/abs/2606.08106)** (Jun 9, cs.AI + cs.MA): statistical acceptance tests for self-evolving agents. The "anytime-valid" framing complements the PIG+ADE "deterministic governance" framing — both answer "is the system still safe?".

- **["Scaling Self-Evolving Agents via Parametric Memory"](https://arxiv.org/abs/2606.04536)** (Jun 9): parametric (not in-context) memory as the substrate for self-evolution. The complementary direction to the SkillBank pattern in this repo.

- **["OpenSkill: Open-World Self-Evolution for LLM Agents"](https://arxiv.org/abs/2606.06741)** (Jun 9, 20 pages): open-world self-evolution. Same direction as Hermes (closed-loop learning + autonomous skill creation) but in an "open world" setting.

- **["Tree-of-Experience"](https://arxiv.org/abs/2606.06960)** (Jun 9): structured experience management for low-repetition, implicit-reward environments. Tree-based indexing as a countermeasure to the cross-session fragmentation the Entropy Principle paper calls out.

- **["Parthenon Law: A Self-Evolving Legal-Agent Framework"](https://arxiv.org/abs/2606.04602)** (Jun 9): domain-specific self-evolution (legal). Evidence that the SkillsVote / EvoMaster pattern is generalizing.

- **["SePO: Self-Evolving Prompt Agent for System Prompt Optimization"](https://arxiv.org/abs/2606.04465)** (Jun 9): system-prompt optimization as a self-evolution target. The LLM-prompt is now just another updatable artifact.

- **["Organizational Control Layer: Governance Infrastructure at the Execution Boundary of LLM Agent Systems"](https://arxiv.org/abs/2606.04306)** (Jun 9): OCL intercepts actions *before* execution via policy enforcement + escalation. Reduces unsafe executions 88% → ~0% and valid success 12% → 96% in adversarial buyer-seller negotiations. Closest direct paper to today's build: same "deterministic governance at the boundary" idea as the Entropy Principle's PIG Engine.

- **["VESTA: A Fully Automated Scenario Generation and Safety Evaluation Framework for LLM Agents"](https://arxiv.org/abs/2606.08531)** (Jun 9): 1,072 evaluation scenarios across 5 risk dimensions; current agents show 47.1% ASR (Attack Success Rate), some >70%. The eval counterpart to the PIG+ADE countermeasure.

- **["Toward Pre-Deployment Assurance for Enterprise AI Agents"](https://arxiv.org/abs/2606.04037)** (Jun 9, v2): ontology-grounded simulation + trust certification. Regulatory coverage 48.3% vs 33.1% for persona-based generation (corrected p=.0006). The "pre-deployment" complement to the Entropy Principle's "runtime monitoring".

- **["Cascading Hallucination in Agentic RAG: The CHARM Framework"](https://arxiv.org/abs/2606.04435)** (Jun 9): cascade detection rate 5.3% FPR, error propagation reduction 82.1% (vs 18.5% output-level). Maps onto the paper's "Channel Fracture" type — but for retrieval pipelines rather than inter-agent messaging.

- **["Multi-Agent Reflexion (MAR)"](https://arxiv.org/abs/2512.20845)** (Dec 2025, v2 Jun 2026): replication of Reflexion exposes systematic confirmation bias and degeneration-of-thought; multi-agent extension with diverse reasoning personas + judge model improves both. Reinforces the MultiAgent `core/multi_agent.py` work.

- **["The End of Software Engineering: How AI Agents Are Fundamentally Restructuring the Software Paradigm"](https://arxiv.org/abs/2606.05608)** (Jun 9): 3-stage evolutionary roadmap (Tool-Augmented 2023-2025 → Single-Task Autonomous 2025-2027 → ...). Stage II = the 2026 production-shift year.

- **["ADK Arena: Evaluating Agent Development Kits via LLM-as-a-Developer"](https://arxiv.org/abs/2606.05548)** (Jun 9): 51 Python ADK frameworks, 204 agent-benchmark pairs. No single framework dominates; best resolves 80% on a single benchmark, median 32%. Documents the fragmentation OpenHive / OpenFang / Hermes / OpenFang / HiClaw are racing to consolidate.

- **AgentScout Weekly Digest (Jun 4 → Jun 10)**: 3 self-evolving agent frameworks (EvoDS, SkillPyramid, EvoDrive) + LAP agent-to-instrument protocol + Constraint State Governance. Same "self-evolving skill library" pattern as our `skills/skill_governance.py` + `core/skill_acquisition.py`.

### Trending Open-Source Repos (Jun 4–10)

- **NousResearch/hermes-agent** v2026.6.5 (Jun 6, 189k stars): single-agent self-improvement, cross-model gateway, TUI, scheduled automations. The most-trending single-agent framework.
- **RightNow-AI/openfang** v0.6.9 (May 2026, 17.8k stars): Rust "Agent OS" with 14 crates, ~137k LOC. The most-trending "agent OS" project.
- **aden-hive/hive** v0.11.0 (May 2026): multi-agent harness with dynamic topology generation.
- **agentscope-ai/HiClaw** v1.1.2 (May 27, 4.7k stars): Kubernetes-native multi-runtime orchestrator (OpenClaw + QwenPaw + Hermes).
- **AMAP-ML/SkillClaw** (Jun 2026, 1.8k stars): collective skill evolution across Hermes, Codex, Claude Code, OpenClaw, etc. Direct parallel to our `skill_coevolution.py` work.
- **Lumio-Research/hermes-agent-rs**: Rust rewrite of Hermes Agent (zero dependencies, single binary).
- **r0b0tlab/hermes-concurrent-agents**: parallel Hermes workers on unified-memory GPUs with SQLite kanban.
- **huggingface/smolagents** v1.26.0 (May 2026, 27.8k stars): lightweight Python library for code-powered agents. Continues to be the "smallest viable agent" reference.
- **open-multi-agent/open-multi-agent** v1.6.0 (Jun 6, 6.3k stars): TypeScript-native multi-agent orchestration for Node.js.
- **open-gitagent/gitagent** v1.4.3 (Apr 22, 525 stars): agent-as-git-repo; identity, rules, memory, tools, skills all version-controlled.
- **verl-project/uni-agent**: Python framework for 1000+ concurrent agent tasks with the same stack for inference and RL training.

### Build Task: Silent Failure Monitor (PIG Engine + ADE Protocol)

**Motivation**: The Entropy Principle paper (arXiv:2606.08162, Jun 9 2026) is the strongest 2026 statement of an under-acknowledged truth: silent failures in LLM agent systems are *not* bugs to be fixed but inevitable consequences of intrinsic properties of language-based agents. S(t) = S0 · exp(α·t) means system entropy *will* grow unless something at the boundary enforces order. The paper's engineering response is a PIG (Physical Integrity Gate) Engine + ADE (Agent Delivery Engineering) protocol suite. This repo already has a `MetacognitiveMonitor` (self-report) and a `SafetyCircuitBreaker` (per-action gate), but neither is a *boundary* monitor with a measurable entropy substrate. Today's build fills the gap.

The work is intentionally small (~800 LOC): we don't replace the `MetacognitiveMonitor` or the `SafetyCircuitBreaker` — we add a third leg of the stool that integrates with both. The monitor is the agent's *self* report; the circuit breaker is the *per-action* check; the silent-failure monitor is the *rolling-window boundary* monitor. They cross-check each other.

**Key Components** (`core/silent_failure_monitor.py`, ~790 lines):

1. **`SilentFailureType`** — enum of the paper's 5 failure types, each tagged with the lifecycle layer (L1/L2/L3) from §2.2 of the paper
2. **`FAILURE_TO_PROPERTIES`** — explicit crosswalk from each failure type to the 22 intrinsic properties (P1–P22) that cause it. The crosswalk is the *causal grounding* layer: when a signal is observed, the audit log records both the type and the property IDs the caller claims
3. **`EntropyConfig`** — per-type `threshold`, `episode_count`, `alpha_cap`, `episode_window_s`. The cap is *operator-controlled* (matching the `BrakePedal` posture from the RSI gate, not auto-tuned)
4. **`EntropySignal`** — a single timestamped (failure_type, value, metric, source, grounding) indicator. `value` is in [0, 1]; `grounding` is a tuple of property IDs from the paper's 22
5. **`EntropyObservation`** — substrate of the audit log: signal + decision + rationale + rolling count + rolling alpha
6. **`FailureEpisode`** — coherence window for a single failure type: opened when the rolling count crosses `episode_count`, closed when the rolling count returns below threshold for the full window
7. **`PIGEngine`** — the boundary gate. Reads signals, tracks rolling entropy per type, returns a deterministic `PIGDecision` (ALLOW / DAMP / BLOCK / ESCALATE). Channel Fracture is the highest-stakes type (priority 5); Behavior Routing Deficiency is the lowest (priority 1)
8. **`ADEProtocol`** — the protocol suite: `monotonic_constraint` (peak-alpha invariant), `episode_window` (bounded duration), `evidence_coherence` (grounding matches property map), `cross_type_damping` (highest-priority type wins)
9. **`SilentFailureMonitor`** — orchestrator. JSONL audit trail on disk, callback hook, batch-observation with `aggregate_decision`. Never mutates the agent; never auto-applies

**Conservative defaults** (per the paper's "fail-loud" framing):
- Channel Fracture: tightest threshold (0.4), BLOCK on first episode
- Cognitive Framework Lag / Data Consistency Decay: threshold 0.5–0.6, DAMP → BLOCK → ESCALATE
- Cross-Session Fragmentation: looser threshold (0.7) — the paper notes this is the slowest to accumulate
- Behavior Routing Deficiency: threshold 0.5, but lowest priority in cross-type decisions
- Recovery: a value below threshold resets the escalation counter and closes the episode

**Test Coverage** (`experiments/test_silent_failure_monitor.py`, ~580 lines): all 44 tests pass ✅
- `TestSilentFailureType` / `TestEntropyConfig` / `TestEntropySignal` — value-object tests (3 + 4 + 2)
- `TestPIGEngineBasicDecision` — below-threshold ALLOW, above-threshold DAMP, episode BLOCK, sustained ESCALATE (4)
- `TestPIGEngineChannelFracture` — BLOCK on first episode for the highest-stakes type, quick escalation (2)
- `TestPIGEngineEpisodeLifecycle` — open, close on recovery, reopen (3)
- `TestPIGEngineGroundingCoherence` — incoherent grounding prefixes rationale; ADE helper (3)
- `TestPIGEngineCrossTypeDamping` — ADE cross-type ladder (4)
- `TestPIGEngineMonotonicConstraint` — ADE monotonic + episode_window (3)
- `TestEntropyAlphaCapEscalation` — alpha cap is recorded + observed on the second episode (1)
- `TestFailureEpisodeDuration` — open/closed duration math (3)
- `TestSilentFailureMonitorAuditTrail` — JSONL persistence, in-memory mode, callback hook (3)
- `TestSilentFailureMonitorRecent` / `TestSilentFailureMonitorSummary` — recent(n), history_for(t), summary state (5)
- `TestSilentFailureMonitorIntegration` — observe_batch + aggregate_decision (3)
- `TestAuditabilityInvariant` — every decision has a rationale; audit file records full state (2)

**Research Synthesis**:
- The Entropy Principle paper is the *first* paper in 2026 to give a single unifying theory for the 130+ failure modes already documented (MAST, Microsoft AIRT, Token Budgets, Latitude, Pazi, BAGEN, Library Drift, etc.). The paper's five-type taxonomy is the substrate; our monitor is the implementation
- The PIG Engine's role is the *same role* as the OCL paper (organizational control layer at the execution boundary) and the same role as our existing `SafetyCircuitBreaker` — but for *rolling-window* drift rather than per-action risk. The three form a triad: (a) per-action (`SafetyCircuitBreaker`), (b) rolling-window boundary (this build), (c) agent self-report (`MetacognitiveMonitor`)
- The 22 intrinsic properties → 5 failure types → 1 PIG decision is a clean compression: we don't need to track 22 properties; we observe 5 types, and the property IDs are in the audit log when the caller wants to do after-the-fact analysis
- The "alpha cap" framing (per-type cap on entropy rate) is the conservative analog of the Anthropic "brake pedal": the operator sets the cap, the engine enforces it, and the cap is *always* in the audit record
- The cross-type priority ladder (Channel Fracture > Cognitive Lag > Data Decay > Cross-Session Frag > Behavior Routing) is the macro policy: when multiple types drift at once, the highest-stakes type wins. This matches the paper's framing of "the deepest layer (memory, transmission) matters more than the surface layer (execution)"
- The monitor's audit trail is JSONL: every signal + decision + rationale is on disk in `<audit_path>/events.jsonl`, matching the pattern of `SkillEvolutionGate` and `SelfReviewQueue` — same substrate, different policies
- The integration points with the rest of the repo (next priority list) close the loop: the RSI gate (Jun 7) + the SkillEvolutionGate (Jun 9) + this monitor = three orthogonal governance layers, all reading the same evidence substrate
- The PIG Engine's design choice — "BLOCK on the boundary, never auto-apply" — is the same posture as the `BrakePedal`: the boundary is deterministic, the policy is operator-controlled, the audit trail is on disk
- The June 10 wave of self-evolution papers (Q-Evolve, Socratic-SWE, OpenSkill, Tree-of-Experience, Parametric Memory) all converge on the same macro pattern that the Entropy Principle paper diagnoses as silent-failure-prone. The monitor is the runtime counterpart to those research advances
- VESTA, the OCL paper, and Pre-Deployment Assurance are the *eval* and *pre-deployment* counterparts to today's *runtime* build. The full picture is: PIG+ADE = runtime boundary, VESTA = safety eval, OCL = execution boundary, Pre-Deployment Assurance = pre-deployment certification
- The `core/recusive_self_improvement.py` `BrakePedal` (Jun 7) and this `PIGEngine` are the same operator-controlled-throttle pattern, applied to two different layers: the *self-edit surface* and the *agent-action boundary*. They don't share code on purpose; they share the *posture*

**Files Changed**:
- `core/silent_failure_monitor.py`: 790 lines (new) — SilentFailureType, FAILURE_TO_PROPERTIES, EntropyConfig, EntropySignal, EntropyObservation, FailureEpisode, PIGEngine, ADEProtocol, SilentFailureMonitor, create_silent_failure_monitor, quick_signal
- `experiments/test_silent_failure_monitor.py`: 580 lines (new) — 44 tests covering all components + ADE protocol + audit-trail JSONL + cross-type priority ladder + conservative defaults
- `CURRENT_RESEARCH.md`: this entry

## Next Priority

- **Wire `PIGEngine.evaluate` into `SafetyCircuitBreaker.should_allow`**: every action decision consults the rolling-window monitor for sustained drift; the circuit breaker becomes both per-action and rolling-window
- **Wire `PIGEngine` into `BaseAgent.run` cycle**: after each EXPLORE/VERIFY/PLAN/EXECUTE/REFLECT step, the agent records an `EntropySignal` from the relevant property (e.g. EXPLORE → Channel Fracture, REFLECT → Cognitive Framework Lag, EXECUTE → Data Consistency Decay)
- **Cross-monitor calibration cross-check**: feed `MetacognitiveMonitor.calibration_signals()` into `PIGEngine` so the engine knows when the agent's *self-report* says "uncertain" and the rolling alpha says "stable" (or vice versa); the disagreement is itself a signal
- **Empirical-alpha fit**: a small experiment that fits the α constant from the existing `proposals/` audit trail (the RSI gate has been writing audit files for 1+ week) and exposes `alpha_cap` as a learned parameter rather than a configured one — operator-tunable, not auto-tuned
- **Pre-deployment assurance bridge**: connect the VESTA / OCL / Pre-Deployment Assurance *eval* systems to the PIG Engine so the engine's decision is informed by the agent's pre-deployment certification; a certified agent gets a wider alpha cap
- **`observe_batch` integration with `MultiAgent.disseminate`**: when the MultiAgent module passes a message between agents, both the sender and the receiver emit a Channel Fracture signal; the monitor's cross-type damping picks the highest priority
- **LatticeAI-style dashboard**: a `python -m core.silent_failure_monitor --summary` CLI that prints the monitor state in color, and a `python -m core.silent_failure_monitor --audit --last 20` filter for the operator's morning review
- **Adversarial entropy injection experiment**: 20 episodes that try to (a) lie about `grounding` to bypass the ADE evidence_coherence check, (b) inflate `value` past the threshold and immediately recover to avoid the rolling window, (c) split a single failure across multiple types to defeat the cross-type damping. Confirm the conservative posture holds

---

*Last updated: 2026-06-10 by AGI Research & Build Agent*
## Research Summary (June 11-12, 2026)

### Industry News & Breakthroughs

- **Three-Ring Architecture: Governing Agents in the Era of On-Platform Organisations** (arXiv:2606.07119, Alvarez-Telena & Diez-Fernandez, Jun 5 2026) ⭐ BUILDS ON THIS
  - Central claim: organisations are acquiring agentic capability without the infrastructure to govern it. Expected to reproduce the 95% GenAI pilot-failure rate. Ring 1 = production (substrate), Ring 2 = M2 federation (strategies-based, deterministic, traceable), Ring 3 = LLM-based frontier intelligence (non-deterministic, propagating, non-traceable)
  - The strongest single sentence: "every improvement in LLM capability is a structural tailwind for this architecture. More capable non-deterministic actors produce larger consequences when they deviate. The governance requirement scales with capability."
  - The federation layer is the *OS* of the agentic enterprise — resource abstraction, process coordination, permission enforcement
  - Direct lineage from the org's Q2 2026 enterprise data (89% obs / 52% evals, MIT 95% pilot failure) and the OWASP GenAI Security Project's "State of Agentic AI Security and Governance" (Jun 3 2026)

- **Autonomous Incident Resolution at Hyperscale (arXiv:2606.09122, Jun 8 2026)** — production-deployed multi-agent framework; >90% autonomous resolution; layered authorization + rollback; structured knowledge from runbooks; closed-loop verification. The runtime case for a permission-bounded federation layer

- **Microsoft Build 2026 follow-on (Jun 5-7) — Microsoft Execution Container (MXC) and MAI-Thinking-1**
  - MXC: kernel-level execution containers for agent containment; the OS-level cousin of our Ring 2 permission gate
  - MAI-Thinking-1: first-party reasoning model, Microsoft decoupling from OpenAI for the model tier
  - Pairs with MDASH multi-agent vulnerability research — the security/eval side of the Three-Ring story
  - Azure Agent Mesh is a federated control plane that *literally routes* agent workloads across Windows, Windows 365, and Azure Arc — same shape as our Three-Ring governor, scaled to enterprise

- **OWASP "State of Agentic AI Security and Governance" (Jun 3 2026)** — security maturity model for multi-agent systems; closes the gap between shipped agents and shipped governance. Borrows Meta's "Rule of two" (an agent should satisfy no more than two of three risky properties in a session without human approval)

- **Vigil — Help Without Being Asked (arXiv:2604.09579)** — deployed proactive on-call agent at Volcano Engine (ByteDance); continuous self-improvement from human-resolved incidents. The deployed case for SkillEvolutionGate + evidence-ledger integration

- **OpenAI files for IPO (Jun 9 2026)** — the AGI mission explicitly stated in the S-1; OpenAI now competing with Anthropic for the personal-agent super-app

- **OpenAI + Visa agentic commerce (Jun 10 2026)** — Visa Intelligent Commerce rails inside ChatGPT; the first "AI agents buy things" production deployment; permission scope (DELEGATE + BROAD) becomes literal money

### Key arXiv / OpenReview Papers (Past 2 Weeks)

- **Three-Ring Architecture (arXiv:2606.07119)** ⭐ BUILDS ON THIS — federation vs. frontier ring split, permission bounds, capability tailwind
- **Autonomous Incident Resolution at Hyperscale (arXiv:2606.09122)** — production-deployed case for the Three-Ring approach
- **AOI (arXiv:2603.03378)** — Observer-Probe-Executor runtime with read-write separation; >24pp gain on AIOpsLab; Trajectory-Corrective Evolver converts 37 failed trajectories into training signals. The closest empirical cousin to our Ring 2 (R2) read/write/execute permission bound
- **Vigil (arXiv:2604.09579)** — proactive on-call agent with continuous self-improvement
- **Memory-as-Governance: PROJECTMEM (arXiv:2606.12329)** — local-first event-sourced memory with a deterministic pre-action gate that warns an agent before repeating a failed fix. The pre-action gate is exactly our `classify_risk` + safety circuit breaker
- **VESTA — safety eval framework (Jun 2026)** — pre-deployment assurance, the *eval* side of the runtime
- **OCL — Organizational Control Layer (arXiv:2606.04306)** — governance infrastructure at the execution boundary; same shape as our Ring 2 permission gate

### Trending Open-Source Repos (multi-agent + governance)

- **microsoft/agent-framework v1.10.0 (Jun 10 2026, 15k+ stars, MIT)** — production-grade multi-agent framework with graph orchestration, checkpointing, streaming, HITL, time-travel. Microsoft / .NET
- **crewAIInc/crewAI v1.14.7 (Jun 11 2026)** — standalone Python multi-agent framework; crews + flows
- **dapr/dapr-agents v1.0.4 (Jun 11 2026)** — Dapr-based durable multi-agent; virtual actors, pub/sub, AIOps-friendly
- **open-multi-agent/open-multi-agent v1.6.0 (Jun 6 2026)** — TypeScript goal-first multi-agent; auto-parallelizes via runtime DAG
- **idea-idsia/ant-ai v1.4.0 (Jun 4 2026)** — Python multi-agent with A2A protocol, lifecycle hooks, MCP, Langfuse
- **sontianye/nexus** — Python multi-agent with graph + router + adaptive modes; 100+ LLM providers via LiteLLM
- **adenhq/hive v0.11.0 (May 2026)** — production-grade multi-agent harness; session isolation, checkpoint recovery, audit trails
- **EvoMap/awesome-agent-evolution** — curated list of self-evolving agents and memory substrates

## Build Task: Three-Ring Architecture (Alvarez-Telena & Diez-Fernandez, arXiv:2606.07119)

**Status**: ✅ COMPLETE - 66/66 tests pass (module was sitting uncommitted on disk; this run picked it up and committed it)

**Motivation**: The Three-Ring Architecture paper is the most concrete 2026 statement of the missing layer between the LLM and the production system. It frames the problem as a 95% project-failure rate (matching MIT's GenAI pilot stat) and proposes a three-layer governance infrastructure: Ring 1 is the existing production architecture (informational), Ring 2 is the M2 federation layer (deterministic, strategies-based, traceable, recoverable), Ring 3 is the LLM-based frontier intelligence layer (non-deterministic, propagating, non-traceable). The paper's strongest claim is *structural*: "every improvement in LLM capability is a structural tailwind for this architecture. More capable non-deterministic actors produce larger consequences when they deviate. The governance requirement scales with capability." Our repo already has the per-action gate (SafetyCircuitBreaker), the rolling-window boundary monitor (PIGEngine / silent_failure_monitor), and the self-report (MetacognitiveMonitor). The Three-Ring governor is the fourth leg: it routes requests through Ring 2 first, only escalates to Ring 3 when Ring 2 flags the request as needing frontier intelligence.

**Key Components** (`core/three_ring_architecture.py`, 1138 lines):

1. **`RingLayer`** (str-enum) — `PRODUCTION` / `FEDERATION` / `FRONTIER`. str-mixins so `RingLayer.FEDERATION == "ring_2_federation"`
2. **`RiskProfile`** — the paper's two-categorical distinction: `DETERMINISTIC` (R2, traceable) / `NON_DETERMINISTIC` (R3, propagating) / `INFORMATIONAL` (R1, substrate). Crosswalked from ring in `RING_TO_RISK`
3. **`PermissionScope`** — `READ` / `WRITE` / `EXECUTE` / `DELEGATE` / `BROAD`. Ring 2 default is (READ, WRITE, EXECUTE); Ring 3 default is (READ, WRITE, EXECUTE, DELEGATE, BROAD). R2 is a strict subset of R3
4. **`CostClass`** — `LOW` (≤1¢) / `MEDIUM` (≤10¢) / `HIGH` (≤$1) / `CRITICAL` (>$1 / cross-system blast). The cost-weighting substrate for the capability-tailwind metric
5. **`AgentDescriptor`** — small, deterministic descriptor of a single agent: name, ring, capabilities, permissions, cost class, deterministic flag, registered_at. `to_dict` / `from_dict` for audit trail round-tripping
6. **`RoutingDecision`** — traceable, audit-logged answer to a routing request. Carries request_id, ring, agent_id, needs_frontier, rationale, capability_required, permission_used, cost_class, timestamp, tailwind_pressure, previous_decision_id. The decision is *never* re-routed silently — re-routing is a fresh decision
7. **`StrategyPlan`** — Ring-2 plan: a sequence of (agent_id, capability) tuples. `needs_frontier=True` is the explicit escalation signal; the plan must carry a `frontier_capability` when it escalates
8. **`FederationLayer`** (Ring 2) — registry of strategies-based agents. Registration is strict: rejects non-Ring-2 agents, rejects non-deterministic agents. `plan(request_id, request, required_capability)` runs a planner_fn (default: capability match → text-match → escalate) and returns a `StrategyPlan`. Plans are stored and retrievable via `plan_for(request_id)`
9. **`FrontierLayer`** (Ring 3) — registry of LLM-actor descriptors. Symmetric strict registration: rejects R2/deterministic agents. `record_invocation(agent_id, cost_class, succeeded)` accumulates tailwind pressure with per-cost-class weights (LOW=1, MEDIUM=3, HIGH=10, CRITICAL=30); success does *not* increment. `invocations(n)` returns the rolling history; filterable by `agent_id`
10. **`CapabilityTailwind`** — descriptive analytical view. `r3_escalation_rate`, `r3_cost_distribution`, `r3_failure_rate`, `summary()`. The `recommendation()` string surfaces one of: HIGH_ESCALATION (>50% of recent R3), HIGH_CRITICAL_COST (any recent R3 was CRITICAL), HIGH_FAILURE_RATE (>30% of recent R3 failed), or OK. The recommendation is the *operator-visible* expression of the paper's "governance scales with capability" claim
11. **`ThreeRingGovernor`** — orchestrator. `route(request, required_capability, request_id, permission)` always asks R2 first; if R2 returns `needs_frontier=True`, consults R3; if R3 has no matching agent, refuses to route and records the refusal. Picks the *lowest-cost* R3 candidate when multiple match. `_record(decision)` appends to the in-memory deque and persists to `<audit_path>/routing.jsonl`. `record_frontier_outcome(decision, succeeded)` updates the frontier tailwind *without* mutating the original decision (the decision and its outcome are two halves of the same event)
12. **Convenience constructors** — `create_three_ring_governor(audit_path)`, `make_ring2_agent(name, capabilities, permissions, cost_class)`, `make_ring3_agent(name, capabilities, permissions, cost_class)`. Default R2 cost class is LOW; default R3 is MEDIUM (the conservative posture: don't default to HIGH/CRITICAL)

**Conservative posture (the paper's macro invariants, baked in)**:
- Ring 2 always plans first. R2's plan is recorded even when R3 ultimately handles the request (so the audit trail always shows the R2 escalation path)
- Ring 3 is *never* a free pass. Every R3 call passes through R2's permission gate (the planner returns `needs_frontier=True` and the R2 plan is stored)
- The governor never auto-escalates from R2 to R3; the routing decision is logged with a rationale the operator can audit
- The lowest-cost R3 candidate is preferred when multiple match (conservative on cost, conservative on consequence)
- An empty R2 plan refuses to route (refusal is logged with the rationale "R2 plan is empty; refusing to route")
- A deregistered agent between plan-and-route is a race that refuses to route ("no longer registered; refusing to route")
- An R3 capability that no frontier agent has is a refusal ("no R3 agent matches; refusing to route")
- The `RoutingDecision` is immutable after `_record`; `record_frontier_outcome` writes a tailwind update *without* mutating the decision

**Audit trail**: every routing decision is persisted to `<audit_path>/routing.jsonl` (one JSON object per line). The `summary()` method returns ring_2_routes, ring_3_routes, federation_size, frontier_size, tailwind_pressure, and audit_path. The audit trail is the substrate for after-the-fact review

**Test Coverage** (`experiments/test_three_ring_architecture.py`, 748 lines): all 66 tests pass ✅
- `TestRingLayer` / `TestRiskProfile` / `TestCostClass` — value-object tests (3 + 1 + 1 = 5)
- `TestPermissionScope` — R2 default is bounded, R3 is broader, R2 is a strict subset of R3 (3)
- `TestAgentDescriptor` — construction, empty-capabilities rejection, dict round-trip, registered_at (4)
- `TestFederationLayer` — empty, register, reject R3, reject non-deterministic, deregister, find_by_capability, plan with R2 match, plan with explicit capability, plan escalation, custom planner, plan_for retrieval, planner type-check (12)
- `TestFrontierLayer` — empty, register, reject R2, reject deterministic, deregister, find_by_capability, tailwind starts at zero, failure increments with cost weighting, cost weight table, invocations history, invocations filter by agent (11)
- `TestThreeRingGovernor` — construction, route R2 match, route R3 when no R2 match, route R3 picks lowest cost, route R3 refuses when no match, empty federation refuses, race deregistered agent, records decision in log, record_frontier_outcome, ignores R2 outcomes, audit trail persists to disk, summary includes all substrate (12)
- `TestRoutingDecision` — to_dict / from_dict round-trip (1)
- `TestStrategyPlan` — basic plan, needs_frontier requires capability (2)
- `TestCapabilityTailwind` — empty summary, recording R3 increments, high escalation, high critical cost, high failure, mixed routes (6)
- `TestConvenienceConstructors` — make_ring2_agent defaults, make_ring3_agent defaults, usable with governor (3)
- `TestConservativePosture` — R2 cannot be in frontier, R3 cannot be in federation, default prefers R2, R3 only when R2 can't, failure increases tailwind but not routes, decision is immutable, governor never calls R3 without R2 planning (7)

**Research Synthesis**:
- The Three-Ring paper is the *macro* frame; our existing SafetyCircuitBreaker, PIGEngine, and MetacognitiveMonitor are the *micro* legs of the stool. The governor is the *router* that sits in front of them: it does not replace them, it routes requests to the right ring
- The Ring 2 / Ring 3 risk distinction maps cleanly onto the permission scope: R2 has bounded scope (READ + WRITE + EXECUTE), R3 has wider scope (plus DELEGATE + BROAD). The wider scope is the *operator-visible* expression of the paper's "more capable non-deterministic actors produce larger consequences when they deviate" claim
- The capability-tailwind metric is descriptive, not predictive. It records what the governor *observes* (escalation rate, R3 cost distribution, R3 failure rate) and surfaces a `recommendation` string. The paper's claim is structural; the metric is the structural-substrate that lets the operator verify the claim after the fact
- The "R2 plans first, R3 only on escalation" conservative posture is the same posture as our `BrakePedal` (RSI gate, Jun 7): the boundary is deterministic, the policy is operator-controlled, the audit trail is on disk
- The `RoutingDecision`'s immutability after `_record` mirrors the `PIGDecision`'s immutability and the `RSIDecision`'s immutability. The audit substrate is *append-only*; the audit trail is the system of record
- The lowest-cost R3 candidate selection is the conservative analog of the `CostClass` weighting in the PIG engine. Both policies say: when in doubt, pick the cheap one
- The federation layer's strict registration (rejecting R3 in R2, rejecting non-deterministic in R2) is the same posture as `classify_risk` promoting any proposal that touches the self surface to CRITICAL. The substrate protects itself
- The `RoutingDecision.previous_decision_id` field is the substrate for re-routing chains: a re-routing is *never* a silent edit, it's a new decision with the old one's ID. This is the same pattern as the proposal-from-improvement-proposal bridge in the RSI gate
- The `create_three_ring_governor(audit_path)` factory is the smallest viable install: federation, frontier, governor, tailwind — four objects, one line. Every other repo's multi-agent framework (CrewAI, dapr-agents, Nexus) starts at 10-100x the size because they conflate the *routing* with the *execution*. The governor is *only* routing; execution is the agents' job
- The 66 tests are intentionally small: each one verifies a single conservative-posture invariant. The conservative posture is the macro invariant; the tests are the micro expressions of that invariant
- The audit-trail JSONL mirrors the pattern of `SkillEvolutionGate` (Jun 9), `SelfReviewQueue` (Jun 9), `SilentFailureMonitor` (Jun 10), and `RSIController` (Jun 7). The substrate is the same: append-only, on-disk, auditable
- The whole module is ~1138 lines: small enough to read in one sitting, large enough to be non-trivial. This matches the EvoMaster / SkillsVote "small, focused, working" discipline

**Files Changed**:
- `core/three_ring_architecture.py`: 1138 lines (new) — RingLayer, RiskProfile, PermissionScope, CostClass, AgentDescriptor, RoutingDecision, StrategyPlan, FederationLayer, FrontierLayer, CapabilityTailwind, ThreeRingGovernor, create_three_ring_governor, make_ring2_agent, make_ring3_agent
- `experiments/test_three_ring_architecture.py`: 748 lines (new) — 66 tests across 11 test classes covering all components + the conservative-posture invariants
- `core/__init__.py`: 17 new public exports for the Three-Ring module
- `CURRENT_RESEARCH.md`: this entry
- `AGENTS.md`: build log entry

## Next Priority

- **Wire `ThreeRingGovernor` into `BaseAgent.run`**: replace the implicit "call LLM" path with an explicit `gov.route(task, required_capability)` call. The agent gets a `RoutingDecision` back; the agent's actual `llm_client` call is gated by `decision.ring == RingLayer.FRONTIER` (i.e. R3 is the only place the LLM is invoked directly; R2 calls are deterministic strategies)
- **Wire `CapabilityTailwind` into `MetacognitiveMonitor.assess_current_state`**: when the tailwind's `recommendation()` returns HIGH_ESCALATION, HIGH_CRITICAL_COST, or HIGH_FAILURE_RATE, the metacog monitor's `should_escalate` flips to True. The cross-check surfaces the operator-visible structural signal in the agent's self-report
- **Wire `ThreeRingGovernor` into the `RSIProposal` risk classifier**: a proposal that targets `core/three_ring_architecture.py` is added to the explicit self-surface list (it is now part of the substrate)
- **CLI / dashboard for the routing decisions**: `python -m core.three_ring_architecture --review` shows the last N routing decisions, the tailwind pressure, and the audit-path JSONL line count
- **Registry bridge to `AgentPool.register_agent`**: when an agent is registered in the federation layer, also register it in the multi-agent `AgentPool` so the governor's R2 routing can be used by the multi-agent orchestrator's `execute()` path
- **Adversarial test pass**: 20 routing attempts that try to (a) escalate to R3 with an empty R2 plan, (b) mutate a recorded RoutingDecision, (c) register a deterministic agent in R3, (d) force the governor to prefer a higher-cost R3 agent when a lower-cost R3 is available. Confirm the conservative posture holds
- **Permission-scope enforcement at the tool layer**: a `RingPermissionEnforcer` that wraps a tool invocation and refuses to execute it if the agent's `permissions` do not include the `permission` the governor recorded. Closes the loop between routing and execution
- **Capability-tailwind cross-feed to `SilentFailureMonitor`**: when the tailwind's `r3_failure_rate` crosses 30%, the monitor's `PIGEngine` raises the alpha cap on `DATA_CONSISTENCY_DECAY` (the failure type that captures cross-agent fidelity loss). The structural signal flows into the rolling-window boundary

---

*Last updated: 2026-06-12 by AGI Research & Build Agent*

---

### 2026-06-13 - Scheduled Run: Proof-Carrying Action (PCA) Bridge

**Status**: ✅ COMPLETE - 47/47 tests passed

**Research Summary (June 13, 2026)**:

The first half of June 2026 produced a striking convergence in agent-governance research. The 2026-06-12 build (`Three-Ring Architecture Governor`) closed the routing layer. Today's build closes the **execution layer** with a portable, certificate-bearing action substrate that ties together every paper from the last two weeks:

- **Proof-Carrying Agent Actions (PCAA, arXiv:2606.04104, Jun 4)**: portable action envelopes, runtime/approval receipts, replay-ready proofs, five-checkpoint workflow (pre-admissibility, action-open, assumption-capture, approval, outcome-closure), externality-aware certificates, enforceability classes. The reference architecture for *this* build.
- **SARC (arXiv:2605.07728, May 2026)**: pre-action gate / action-time monitor / post-action auditor / escalation router; regulatory obligations compiled into runtime constraints. The four-enforcement-site pattern is mirrored in our five checkpoints.
- **OpenKedge (arXiv:2604.08601)**: Intent-to-Execution Evidence Chain (IEEC) with cryptographically linked proposal -> approval -> outcome. The hash-chained step ledger is the **system of record** for executed actions.
- **Proposal-Certification-Execution (arXiv:2605.24462)**: L_exec = L_G ∩ L_cert(M_Pi) — execution is conditioned on a certified trace. The cert gate is the *only* path to execution; bare actions stay possible for back-compat.
- **SentinelAgent DCC/IPDP (arXiv:2604.02767)**: Delegation Chain Calculus with P6 (scope-action conformance) and P7 (output schema conformance). The `EnforceabilityClass` enum is our P6; the `record_outcome` step is our P7.
- **Notarized Agents / Sello (arXiv:2606.04193)**: witness-cosigned public transparency log for agent actions. The `enable_audit` IEEC JSONL is our Sello substrate (single-witness for now; multi-witness is a Q3 follow-up).
- **Provably Secure Agent Guardrail / ePCA (arXiv:2605.29251)**: J_ePCA payload, SMT-solver enforcement, `C = s ∧ [[j]]_SMT ∧ Phi_safe`. We do not invoke an SMT solver — we keep the substrate LLM-agnostic and deterministic — but the *shape* (typed payload + verification formula) is mirrored in the `evidence_digest` over (intent + externality).
- **Autonomous Incident Resolution at Hyperscale (arXiv:2606.09122)**: layered authorization + rollback. `ReversalBound` + `EnforceabilityClass` + `close` IEEC step are the layered authorization.
- **Three-Ring Architecture (arXiv:2606.07119, Jun 5)**: federation vs frontier ring split. The bridge carries the `ring_layer` field on every certificate and uses it in the admissibility decision tree.
- **Oversight Has a Capacity (arXiv:2606.08919)**: subjective, fatiguing human guard; inverted-U between escalation and safety. The conservative posture (Ring 3 always requires human; critical cost class always requires human) is the operator-controlled knob — the bridge does not try to model the inverted-U, it just makes the floor strict.
- **Constitutional AI + SafetyCircuitBreaker (existing)**: `policy_ids` on `ApprovalReceipt` lets the bridge cite the policy that approved the action. `require_human_for_ring3` defaults to `True` — Ring 3 frontier always needs a human.

**Industry news (June 13)**:
- **OpenAI files for IPO** (Jun 9) with AGI mission in S-1 — the operator-facing posture of "ambient authority" is now under SEC scrutiny
- **AGIBOT World Challenge 2026** (Shanghai, 526 teams, 27 countries) — embodied AI moving from simulation to closed-loop real-robot testing
- **Microsoft Build 2026 follow-on** (Jun 5-7): MXC runtime containment, MAI-Thinking-1, Azure Agent Mesh — Microsoft's federation layer is the production cousin of our governor
- **CISO Daily Briefing (Jun 9)**: 1-in-8 AI breaches is now agentic; 73% of orgs have unresolved AI security ownership — the substrate for this build is exactly the gap they are reporting
- **VISA Intelligent Commerce rails inside ChatGPT** (Jun 10) — permission scope (DELEGATE + BROAD) becomes literal money; `ReversalBound.IRREVERSIBLE` + `DataClassification.RESTRICTED` is the conservative human-gate
- **HiddenLayer 2026 AI Threat Landscape Report** — agent governance maturity is now a primary risk metric

**Trending open-source repos (Jun 13)**:
- **microsoft/agent-governance-toolkit v4.0.0** (Jun 9) — TEE keystore, Entra-signed JWT, wire-protocol policy evaluation across SQL+K8s, AGT CLI with OWASP verification
- **cordum-io/cordum v1.1.0** (Jun 2026) — Cordum Agent Protocol, pre-execution policy + approval gates + audit trails, edge compliance firewall
- **Orvek-dev/Zeus v1.0.0-alpha.7** (Jun 13) — local-first gate-based governance control plane, 102 frozen tests across gates 0-4, real OS-level enforcement in Q3
- **cunardai/agp-protocol v0.5.1** — Autonomous Governance Protocol, hash-chained immutable audit ledger, taint tracking, EU AI Act OPA policies, 200+ conformance tests
- **SIDJUA v1.1** (GoetzKohlberg, Apr 2026) — 5-stage pre-action enforcement pipeline, EU AI Act mappings, in-app self-update via Go sidecar
- **govAgent v1.x** (thekakodkar) — three-stage enforcement (privacy/semantic/fiscal), immutable forensic session snapshots, MetaGovernor for self-healing policy updates
- **ACR (AI Control Ring) v1.1.0** — runtime control plane, <200ms evaluation endpoint, 160+ unit tests, 6 governance pillars

**Build Task: Proof-Carrying Action (PCA) Bridge**

**Motivation**: The June 12 build (`ThreeRingGovernor`) routes a request through Ring 2 first, escalates to Ring 3 when Ring 2 flags it. But the *execution* path was still implicit: an action was proposed, verified, and executed without a portable artifact that an operator could replay, an auditor could inspect, or a downstream tool could chain off of. Every paper in the last two weeks has independently landed on the same idea: **actions must carry a portable, certificate-bearing substrate that survives across runtimes, vendors, and audit boundaries**. The PCA Bridge is the implementation.

**Key Components**:

1. **`ActionCertificate`** — the portable, system-of-record artifact for a single action. Carries the action's intent, the externality context, the checkpoints, the approval receipt, the evidence digest, and (after closure) the outcome. Immutable after `CertificateState.CLOSED/REJECTED/ABANDONED`. `to_dict` / `from_dict` round-trip preserves every field.

2. **`ExternalityContext` + `ExternalityPolicy`** — PCAA's "boundary facts" as a first-class dataclass: destination_visibility (local/network/external), provenance (user/system/derived), cost_class (low/medium/high/critical), data_classification (PUBLIC/INTERNAL/CONFIDENTIAL/RESTRICTED), reversal_bound (TRANSIENT/REVERSIBLE/IRREVERSIBLE), requires_audit. `ExternalityPolicy.missing_fields` treats empty strings as missing (conservative).

3. **Five checkpoints** (`CheckpointKind`): PRE_ADMISSIBILITY, ACTION_OPEN, ASSUMPTION_CAPTURE, APPROVAL, OUTCOME_CLOSURE. Each `Checkpoint` is immutable once created. The `verify_certificate` method re-validates the ordering, the digest, and the closed-state invariants.

4. **`EnforceabilityClass`** — PCAA's enforceability classes, not a single boolean: REQUIRE_HUMAN, REQUIRE_BRIDGE, POLICY_ONLY, AUTO. Ring 3 frontier defaults to REQUIRE_HUMAN; Ring 2 bounded reads default to AUTO; external destination visibility triggers REQUIRE_BRIDGE; critical cost class triggers REQUIRE_HUMAN; reversible+confidential+irreversible triggers a hard human gate.

5. **`IEECStep` + hash chain** — the Intent-to-Execution Evidence Chain. Each step computes `digest = SHA-256(prev_digest + canonical_payload + sequence + event + ts)`; tampering with any step invalidates every later step. `verify_ieec` re-walks the chain. The chain is append-only and on-disk-auditable via `enable_audit(audit_path)` (writes to `ieec.jsonl`).

6. **`AdmissibilityDecision` / `AdmissibilityVerdict`** — the decision tree: ADMISSIBLE / REQUIRES_BRIDGE / REQUIRES_HUMAN / REJECTED. The conservative posture is **never** a free pass for irreversible + restricted; **always** a human for ring 3 by default; **never** a silent skip on missing externality.

7. **`ProofCarryingActionBridge`** — the orchestrator. `propose` runs pre-admissibility + records three checkpoints + computes the evidence digest; `approve` records the APPROVAL checkpoint and the approval receipt; `execute` runs the registered executor and writes the EXECUTE_START + CLOSE IEEC steps; `record_outcome` is the path for long-running executors. `verify_certificate` + `verify_ieec` + `replay` are the operator surfaces.

8. **`create_pca_bridge(audit_path)`** — the smallest viable install: 1 line, 1 IEEC dir, 1 bridge. ~1100 LOC module, ~820 LOC test file.

**Conservative posture (the bridge's macro invariants)**:
- Execution is *gated* on a valid certificate. The bridge certifies; it does not execute.
- An `ActionCertificate` is immutable after `CLOSED/REJECTED/ABANDONED`. `add_checkpoint` refuses to mutate.
- An `IEECStep`'s digest is recomputed at verify time. Tampering with payload without recomputing digest is detected.
- Empty externality fields count as missing. The bridge never approves a certificate with a blank cost_class.
- Ring 3 frontier + human default: `require_human_for_ring3=True` is the default. The default is **strict**.
- IRREVERSIBLE + RESTRICTED is a hard human gate (SARC: zero hard-constraint violations required).
- Always-human-gated action types (`delete`, `drop`, `truncate`, `send_money`, `self_modify`, `purge`, `kill`, `force_push`) are always human-gated, regardless of ring layer or cost class.
- The `outcome` field is set once, at `execute` or `record_outcome` time. The certificate does not gain an outcome after closure.
- The `approval` receipt carries `policy_ids` and `claim_ids` — the operator can trace an approval back to a specific policy and a specific evidence-ledger claim.
- The audit file is JSONL, one IEEC step per line, machine-parseable for replay. `enable_audit` is opt-in but default-friendly.

**Test Coverage**: 47/47 tests passed ✅
- TestExternalityPolicy: 4 tests (default required fields, complete, round-trip, custom required)
- TestDigestHelpers: 3 tests (stable across key order, value change, excludes checkpoints)
- TestAdmissibilityRouting: 9 tests (R2 read, R3 default, R3 with bridge, external destination, critical cost, irreversible confidential, delete always human, send_money always human, R1 default)
- TestExternalityRequired: 2 tests (missing externality rejects, partial externality rejected with conservative posture)
- TestApprovalFlow: 7 tests (approve admissible, approve pending, approve with policy/claim/routing refs, unknown cert, reject pending, reject immutable, abandon)
- TestExecuteAndOutcome: 5 tests (executor success, no executor, not approved, post-close record, executor exception)
- TestIEECChain: 5 tests (chain starts empty, chain links, verify ok, tampering detected, replay)
- TestAudit: 2 tests (audit file created + appended, audit records full lifecycle)
- TestCertificateVerification: 3 tests (happy path, digest mutation detected, pending-approval doesn't require APPROVAL checkpoint)
- TestSerialization: 1 test (round-trip)
- TestConservativePosture: 4 tests (irreversible never auto, immutable after close, IEEC first step has empty prev, summary counts)
- TestVerifiableActionIntegration: 2 tests (writeable action, full chain of four certificates)

**Research Synthesis**:
- The June 2026 convergence on **portable, certificate-bearing actions** is the most concrete signal of the maturation of agent governance. The PCA Bridge is our implementation of the convergence.
- The **two-timescale** split is preserved: `require_human_for_ring3` and `externality_policy` are the *operator-controlled* slow loop; the admissibility decision tree is the *system-controlled* fast loop.
- The **IEEC hash chain** is the substrate for **replay-ready proofs** (PCAA) and **witness-cosigned transparency** (Sello). We do one-witness now (the bridge itself); multi-witness is a Q3 follow-up.
- The **`EnforceabilityClass` enum** is the *implementation* of the "rule of two" pattern (Meta, OWASP, Three-Ring): an action can be BOTH high-trust and high-consequence, and the bridge maps that to REQUIRE_HUMAN.
- The **`ReversalBound`** + **`DataClassification`** matrix is the *conservative* version of the "safety-utility tradeoff" (OCL paper): the bridge prefers the higher-strictness corner.
- The **`propose + approve + execute + close`** IEEC shape is the *workflow-level* version of the "Pre-Action Gate / Action-Time Monitor / Post-Action Auditor / Escalation Router" SARC pattern. We have *one* site per IEEC step rather than four sites per agent loop, but the audit trail is identical.
- The **`ApprovalReceipt.policy_ids` + `claim_ids`** is the *bridge* between the PCAA certificate and our existing **SafetyCircuitBreaker** (`policy_ids`) + **EvidenceLedger** (`claim_ids`). The certificate is the *portable* form; the existing substrates are the *source of truth*. The next priority is to wire `propose()` to consume the breaker's verdict and the ledger's claims.
- The **`digest_certificate` function** deliberately excludes checkpoints, approval, state, and outcome. The digest is over the *thing the certificate authorises*, not the *way it was authorised*. This is the conservative posture: the auditor can recompute the digest at any time without knowing the IEEC history.
- The **`admissibility_verdict`** decision tree is the *fast loop* of the bridge. The **`require_human_for_ring3` + `ExternalityPolicy`** are the *slow loop*. The bridge does not try to make the slow loop automatic — that's the operator's job, per the Three-Ring paper.
- The **47 tests** are intentionally small: each one verifies a single conservative-posture invariant. The total coverage is *bounded* (~10 minutes to read, ~10 seconds to run).
- The new module is ~1118 lines: small enough to read in one sitting, large enough to be non-trivial. Matches EvoMaster / SkillsVote / Three-Ring "small, focused, working" discipline.

**Files Changed**:
- `core/proof_carrying_action.py`: 1118 lines (new) — ActionCertificate, AdmissibilityDecision, AdmissibilityVerdict, ApprovalReceipt, CertificateState, Checkpoint, CheckpointKind, DataClassification, EnforceabilityClass, ExternalityContext, ExternalityPolicy, IEECStep, ProofCarryingActionBridge, ReversalBound, canonical_hash, create_pca_bridge, digest_certificate
- `experiments/test_proof_carrying_action.py`: 822 lines (new) — 47 tests across 11 test classes
- `core/__init__.py`: 18 new public exports
- `CURRENT_RESEARCH.md`: this build log entry
- `AGENTS.md`: build log entry (next)

**Next Priority**:
- **Wire `ProofCarryingActionBridge.propose()` to consume `SafetyCircuitBreaker.assess_risk()`**: the `AdmissibilityVerdict` should be cross-checked against the breaker's risk classification; an action that the breaker gates as CRITICAL should not be auto-approved even if the bridge would otherwise say ADMISSIBLE/AUTO
- **Bridge to `EvidenceLedger`**: `ApprovalReceipt.claim_ids` is the substrate; the next step is a `propose_with_evidence(action_id, ..., claim_ids=[...])` convenience that pulls the latest SUPPORTED claim IDs from the ledger and pre-fills the receipt
- **`ThreeRingGovernor.route()` -> `ActionCertificate.ring_layer`**: when the governor routes a request to a ring, the certificate should be initialized with that ring layer; a Ring 3 route should always be REQUIRE_HUMAN by default
- **Adversarial test pass**: 20 certificates that try to (a) execute without approval, (b) tamper with a closed certificate, (c) hide a chain step, (d) approve themselves via a self-issued receipt, (e) skip an externality field. Confirm the conservative posture holds
- **Cross-process replay**: an `ieec_replay.py` CLI that reads `ieec.jsonl` from disk and re-validates the hash chain; useful for an external auditor that should not trust the in-process `verify_ieec`
- **Multi-witness notarization (Sello)**: route the IEEC step to an external log (e.g., a witness daemon) and require two-of-three witness signatures before CLOSED
- **LLM-backed `EnforceabilityClass` recommendation**: keep the operator's `require_human_for_ring3` as the *floor*; use a small LLM prompt to *suggest* an EnforceabilityClass for borderline cases, with the bridge requiring the human to over-ride
- **Wire the bridge into `VerifiableActionLoop.propose_action`**: every `VerifiableAction` produced by the loop carries a corresponding `ActionCertificate`. The action is *only* executed if `bridge.execute(cert.certificate_id)` succeeds.

---

*Last updated: 2026-06-13 by AGI Research & Build Agent*
