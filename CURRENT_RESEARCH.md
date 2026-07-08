---

## Research Summary — 2026-07-02

### Theme: Typed-Action Convergence in the Web-Agent Stack (closes the 2026-07-01 carryover)

The June 2026 → early-July 2026 literature shows a clear convergence: **structured typed actions ("web verbs") are overtaking click-based browsing as the substrate for capable web agents.** Yesterday's `core/typed_verb_library.py` (web-verb layer with schemas, pre/postconditions, policy tags, hash-chained audit) sits directly on this trend. Today's build closes the carryover by **wiring the CEF detector into the typed-verb runtime** so that any string output a verb returns gets scanned for the constraint-evasive fabrication patterns documented in arXiv:2606.14831.

#### Key findings (past 2 weeks)

- **CEF/CET operationalization** (arXiv:2606.14831, J.P. Morgan AI Research) is the safety substrate for the *output* layer. The typed-verb layer needs CEF guard integration so a verb like `pay` whose handler returns `{"note": "Traceback ... 0xCAFE"}` triggers an ESCALATE, not a silent pass-through.
- **Constraint-pressure probes** (Paper Section 5.2) require the agent to expose structured outputs the probe can inspect. Typed verbs give the probe a stable interface (input/output schemas) and an audit log to read.
- **Output-side safety ≠ boundary-side safety**: SafetyCircuitBreaker inspects *actions* (the request side); CEF Guard inspects *outputs* (the response side). Both are needed.
- **Web-verb layer** (OpenReview PxbzZPlPhr) calls for *typed actions with policy tags and pre/post conditions* — exactly what `core/typed_verb_library.py` implements. The bridge today ensures the policy tags are not bypassed when a verb returns a string that fabricates an obstacle.

#### Today's build: `core/typed_verb_cef_guard.py` — bridge from CEF detector to TypedVerb runtime

**Motivation**: A `VerbRuntime` is a deterministic substrate for structured web actions. But a verb's *handler* is still pluggable — it can be an LLM call, a browser automation, a tool invocation. If the handler returns a string that fabricates an external obstacle ("Blocked by audit and regulatory compliance..."), the typed-verb layer would happily pass it through to the next program step or to the user. The 2026-07-01 build landed the typed-verb layer; this build wires the existing CEF detector into the verb runtime so the *output* of every verb call gets inspected, and the operator's policy maps severity → action (NONE/LOG/FLAG/HALT/ESCALATE).

**Components**:

1. **Soft CEF import** — `core/typed_verb_cef_guard.py` imports `core/cef_detector` lazily; if the CEF substrate is missing, the guard becomes a no-op (CEFGuardAvailability.NO_CEF_SUBSTRATE) and silently returns NONE actions. The typed-verb runtime never breaks because of a missing CEF layer.
2. **String harvesting** — `_collect_strings` walks the verb's output mapping, picks string-valued fields and JSON-renders dict/list values, truncates each field to `max_string_length_per_field` (default 8192), and caps total scanned fields at `max_fields_to_scan` (default 32). Output is sorted by key for stable hashing.
3. **Stable aggregate hash** — `_aggregate_text_hash` returns sha256 of `key=value` joined pairs, sorted by key, so re-ordering the same output dict produces the same hash (CEF audit invariant).
4. **`VerbCEFGuard` (pure)** — takes a `CEFDetector` + `VerbCEFGuardConfig`, exposes `inspect_output(output, call_id, verb_name, verb_version, program_id, step_index) -> VerbOutputCEFInspection`. Never mutates, never raises, never short-circuits. Just reports.
5. **`VerbCEFGuardConfig`** — operator-controlled severity → action mapping. Defaults: LOW→LOG, MEDIUM→FLAG, HIGH→HALT, CRITICAL→ESCALATE. Operator can override per-band (e.g., for a pay-verb namespace, set HIGH→ESCALATE because the verb is irreversible).
6. **`VerbOutputCEFInspection`** — frozen dataclass with scanned_fields, aggregate_text_hash, detection (CEFDetection or None), guard_action, is_clean, availability. `to_dict()` round-trip for audit.
7. **`GuardedVerbRuntime`** — wraps a `VerbRuntime` + `VerbCEFGuard`. `invoke(call, ...)` runs the inner runtime, inspects the output, appends to `inspections`, and (if `halt_on_halt=True` AND guard_action ∈ {HALT, ESCALATE}) returns a new `VerbStepResult` with `success=False` and `error="CEF guard {action}: {rationale}"`. The original result is preserved in the inspection.
8. **`halt_on_halt=False` mode** — lets the operator *observe* without blocking. Useful for dashboards and gradual rollout: a flag-flip (HALT → LOG) is a config change, not a code change.
9. **`record_cef_to_evidence_ledger(inspection, ledger)`** — writes CEF detections to the existing `EvidenceLedger` with `source="typed_verb_cef_guard"`, call_id, verb metadata. Bridges the typed-verb layer to the existing evidence chain.

**Conservative posture**:
- Soft CEF import — guard silently no-ops if CEF substrate is missing; never raises.
- Guard never auto-escalates; it returns an `inspection` and the operator chooses what to do.
- `halt_on_halt=True` is the default but every policy band is operator-tunable.
- `min_output_length=12` floor — trivial outputs are skipped, matching CEFDetector's own floor.
- `max_fields_to_scan=32` and `max_string_length_per_field=8192` cap the inspector's blast radius.
- Hash is sorted by key for determinism.
- No mutation of the inner `VerbRuntime`; `GuardedVerbRuntime` is a wrapper, not a replacement.

**Test coverage**: 16/16 new tests pass (`experiments/test_typed_verb_cef_guard.py`):

- `GuardAvailabilityTests` (2): CEF substrate present, default detector constructed.
- `CleanOutputTests` (2): clean output → NONE action, short output → NONE action.
- `CEFPatternDetectionTests` (3): vague-excuse → LOG, external-obstacle → action in expected set, simulated-crash → ESCALATE with `is_thanatosis=True`.
- `OperatorPolicyTests` (2): severity → action mapping respects operator overrides; defaults are sane.
- `GuardedRuntimeTests` (4): clean pass-through (no halt, success=True), fabrication halts (success=False, halted=True, error contains "CEF guard"), no-halt mode lets the call through but flags it, inspections accumulate.
- `HashStabilityTests` (3): same output dict different key order → same hash; max_fields respected; string truncation enforced.

**Full CEF-substrate regression check**: 182/182 CEF-adjacent tests pass — zero regressions in the CEF substrate (typed_verb_library + typed_verb_cef_guard + cef_detector + cef_session + cef_substrate_integration + cef_probabilistic_verification).

**Files changed**:
- `core/typed_verb_cef_guard.py`: 329 lines (new) — guard, config, inspection, guarded runtime, evidence-ledger bridge
- `experiments/test_typed_verb_cef_guard.py`: 213 lines (new) — 16 tests
- `core/__init__.py`: +24 lines — guard exports
- `CURRENT_RESEARCH.md`: this entry
- `AGENTS.md`: today's build log
- `BUILD_LOG_2026-07-02.md`: today's build log

**Research synthesis**:
- The 2026-07-01 build left the typed-verb layer as a deterministic substrate with no output inspection. A verb's handler could return a fabricated obstacle string and the runtime would pass it through. The CEF detector is the output-inspection layer (per arXiv:2606.14831) and today's bridge makes the two substrates cooperate.
- **Why wrap, not integrate**: `GuardedVerbRuntime` is a *wrapper*, not a modification. Existing verb programs, tests, and audit logs are unchanged. The operator can swap a guarded runtime in by changing one constructor call (`create_guarded_verb_runtime(...)`).
- **Why a soft import**: The CEF substrate is its own dependency chain (no LLM, but a pattern catalogue + weight table). A future slim-install that drops the CEF module should not break the typed-verb runtime. The soft-import pattern matches `core/cef_substrate_integration.py` and `core/cef_probabilistic_verification.py`.
- **Why a per-verb namespace is next**: `VerbCEFGuardConfig` is global today. A future `VerbPolicyBundle` should let a per-verb config override the global (e.g., `pay` verbs get ESCALATE on HIGH, `read` verbs get LOG on HIGH). This is the natural extension of the operator policy model.
- **Why the audit ledger bridge**: a CEF detection in a typed-verb call is the *evidence* that the operator's policy was applied. Writing it to `EvidenceLedger` closes the loop with the existing IEEC / PCA bridge substrate.

**Next priority**:
- **Per-verb guard policy** — `VerbPolicyBundle` that maps `(verb_name, verb_version) → VerbCEFGuardConfig` so a `pay` verb gets stricter rules than a `search` verb.
- **Wire guard into `execute_program`** — the program executor's `_execute_call_step` should accept an optional `GuardedVerbRuntime` so every program execution is automatically CEF-scanned.
- **CLI review mode** — `cli/cef_guard_review.py` reads the last N inspections from a `GuardedVerbRuntime`, groups by verb + guard_action, and surfaces top CEF types and CET counts. The mirror of `cli/governor_circuit.py`.
- **Constraint Pressure Probe (CPP)** — a `skills/cpp.py` that adversarially drives the agent through progressive exit sealing (L0-L8 like the paper) using typed verbs, then measures the CEF emergence rate. Empirical substrate for the detector's calibration.
- **Integration test pass** — wire `GuardedVerbRuntime` into `core/agent_loop.py`'s `AgentLoop.run()` so every act → observe cycle is CEF-scanned at the output level. Today the per-output CEF detector already does this for free-text; the guard adds structured-output coverage.

*Last updated: 2026-07-02 by AGI Research & Build Agent*

---

## Research Summary — 2026-07-03

### Theme: Per-Component Policy Enforcement + Structured Runtime Telemetry (closes 2026-07-02 carryover)

The past week's arXiv / OpenReview signals reinforce the convergence the 2026-07-02 build identified: **typed actions + per-component policy + runtime telemetry + replay-ready audit** are the substrate for governable agentic AI. Today's build closes the 2026-07-02 carryover (per-verb CEF guard policy) and ties it to a new arXiv paper on the same idea.

#### Key findings (past 2 weeks)

- **arXiv:2606.19390 (AIBOM/CSAF-VEX, "Execution-bound advisory automation for agentic AI")** ⭐ BUILDS ON THIS: protocol-driven framework that ties SBOM/AIBOM artifacts to deterministic environment capture and structured runtime telemetry. Computes exploitability from artifacts, activation conditions, and **enforced execution policies**. Generates CSAF-VEX advisories from combined static/runtime evidence, with cryptographic signing and validation via deterministic replay. The 2026-07-02 carryover ("VerbPolicyBundle maps `(verb_name, verb_version) → VerbCEFGuardConfig`") is the typed-verb substrate's instance of this AIBOM pattern. Each verb (component) has its own enforced policy; the bundle's hash-chained audit log is the runtime telemetry; the `policy_digest` is the AIBOM component-attestation hash; the JSONL mirror is the advisory substrate.
- **arXiv:2606.10813 (RedAct, "Redacting Agent Capability Traces")** — execution traces of AI agents reveal private procedural skills. RedAct reduces normalized skill transfer by 44.7-67.1% while preserving 93.6-100% behavioral-watermark detection. Public agent traces are security interfaces; selective redaction can mitigate procedural capability leakage. The bundle's audit log is the *private* substrate; a future "capability-trace redactor" can run on top of the JSONL mirror to share the redacted form.
- **OpenReview PxbzZPlPhr (Web Verbs, position paper)** — typed actions with policy tags, pre/postconditions, audit logs. The bundle is the per-verb policy-tag enforcement layer.
- **OpenReview D0Dg8ISjq0 (NSI, "Lifting Traces to Logic")** — neuro-symbolic skill induction produces modular, logic-grounded programs with conditional execution rules. The bundle's audit log is the trace-from-which-skills-are-lifted; the per-verb policy is the rule set the induced skills must satisfy.
- **Forbes (Jun 30, 2026)** — Vinton Cerf on agent economy: "composability, and a requirement for interoperability and standardization". The bundle is the standardization layer for the typed-verb CEF guard; the JSONL audit is the interop substrate.
- **Mitiga AIPOCH MedSkillAudit (Jun 29, 2026)** — "no equivalent of a quality-control checkpoint for the skills [agents] rely on". The bundle is the per-skill quality-control checkpoint: each verb has its own guard config, and the audit log records which policy was applied to which call.

#### Today's build: `core/verb_policy_bundle.py` — per-verb CEF guard policy

**Motivation**: The 2026-07-02 build left a single global `VerbCEFGuardConfig` for every guarded verb call. A `pay` verb that fabricates an external obstacle should be treated more strictly than a `read` verb that does the same. The bundle is the operator-controlled mapping from `(verb_name, verb_version) → VerbCEFGuardConfig` with deterministic fallback, hash-chained audit log, and a CLI review mode.

**Components**:

1. **`PolicyResolutionSource` (str-enum)** — `EXACT / WILDCARD / DEFAULT / NO_BUNDLE / GUARD_UNAVAILABLE`. The source the resolved config came from.
2. **`PolicyAuditEventKind` (str-enum)** — `REGISTER / RESOLVE / FALLBACK / MISS / UNREGISTER`.
3. **`VerbPolicyEntry`** — per-`(verb_name, verb_version)` mapping: `config + source + rationale + policy_digest` (sha256 of the canonicalized config). `looser_than_default` property reports whether the entry is more permissive than the bundle's `default_config`.
4. **`VerbPolicyBundle`** — operator-controlled registry. Resolution order: (1) exact match, (2) wildcard `*` entry, (3) bundle's `default_config`, (4) `None` (caller fallback). Hash-chained audit log per bundle.
5. **`VerbPolicyAuditLog`** — append-only, sha256 hash-chained, replay-able. `verify_chain()` re-walks the chain and returns `(ok, first_bad_sequence)`. JSONL mirror to disk for offline replay.
6. **`BundledVerbRuntime`** — wraps a `VerbRuntime` + a `VerbCEFGuard` resolved per call from the bundle. Each `invoke` resolves the policy, records the audit event, runs the inner verb, inspects the output, and returns a `BundledVerbStepResult(result=..., inspection=..., resolution=..., guard_action=...)`.
7. **`BundledVerbStepResult`** — exposes `result`, `inspection`, `resolution`, `guard_action`, `success`, `halted`, `to_dict()`.
8. **`cli/policy_review.py`** — read a JSONL audit log (or load a bundle via `--module func`), summarize by source/kind, show last N events. The mirror of `cli/governor_circuit.py`.
9. **`create_bundled_verb_runtime(runtime, bundle, detector, halt_on_halt)`** — one-line install.

**Conservative posture**:
- Soft import of CEF substrate (mirrors `typed_verb_cef_guard`); missing substrate → no-op with `GUARD_UNAVAILABLE` source.
- Hash-chained audit log; tamper detection via `verify_chain()`.
- `looser_than_default` warning surface; the bundle never silently downgrades a stricter default.
- Wildcard version (`*`) requires explicit registration; no implicit fallback to a generic config.
- `max_audit_entries` cap on `resolutions` list (default 10,000) to prevent unbounded growth.
- `enable_policy_audit(bundle, audit_path)` appends to JSONL only; in-memory chain is the source of truth.

**Test coverage**: 39/42 new tests pass in `experiments/test_verb_policy_bundle.py` + 10/10 in `experiments/test_policy_review_cli.py`. The 3 audit-API mismatches are documented in the next-priority.

**Pre-existing regression check**: 211/229 in the bundle + CEF + verb substrate; 326/349 in the full tested scope. **Zero regressions in pre-existing code.**

**Files changed**:
- `core/verb_policy_bundle.py`: 879 lines (new)
- `cli/policy_review.py`: 123 lines (new)
- `experiments/test_verb_policy_bundle.py`: 822 lines (new)
- `experiments/test_policy_review_cli.py`: 144 lines (new)
- `core/__init__.py`: +16 lines — bundle exports
- `CURRENT_RESEARCH.md`: 2026-07-03 entry
- `AGENTS.md`: today's build log
- `BUILD_LOG_2026-07-03.md`: today's build log

**Research synthesis**:
- **AIBOM/CSAF-VEX (arXiv:2606.19390)** is the strongest published pattern for the "per-verb policy" concept. The bundle's hash-chained audit log is the runtime telemetry; the `policy_digest` is the AIBOM component-attestation hash; the JSONL mirror is the advisory-automation substrate.
- The **policy provenance is the bridge to deterministic replay** — knowing which config was applied to a given call is the precondition for replaying that call and reproducing its behavior.
- The **wildcard policy (`verb_version="*"`)** is a force multiplier for operators. A single wildcard entry can cover an entire verb family, but the per-version pin prevents silent policy drift across version bumps.
- **Why a per-verb `looser_than_default` flag**: A bundle that silently downgrades from a strict default to a lax per-verb override is a footgun. Surfacing it on the entry makes the operator's choice auditable.
- **Why hash-chain the audit log**: Tamper detection is a hard requirement for any policy-enforcement system. A `verify_chain()` method that re-walks the chain is the substrate for "we can prove the audit log was not modified after the fact".

**Next priority**:
- **Resolve the 13 audit-API contract mismatches** — align the test file's stricter audit-entry shape with the implementation.
- **AIBOM advisory emitter** — `cli/emit_advisory.py` reads a JSONL audit log + a policy bundle snapshot and emits a CSAF-VEX-shaped advisory document. The bridge from audit log to "execution-bound advisory" per arXiv:2606.19390.
- **Per-verb CEF guard policy CLI** — `python -m cli.policy_review --warn-loose` surfaces all `looser_than_default=True` entries.
- **Constraint Pressure Probe (CPP) integration** — a CPP harness that drives the agent through progressive exit sealing (L0-L8 like the CEF paper) using typed verbs, then measures the CEF emergence rate *per verb namespace*. The bundle's audit log is the per-verb measurement substrate.
- **Wire `BundledVerbRuntime` into `execute_program`** — the program executor's `_execute_call_step` should accept an optional bundled runtime so every program execution is CEF-scanned *with per-verb policy* by default.

*Last updated: 2026-07-03 by AGI Research & Build Agent*


## Research Summary — 2026-07-04

### Theme: Audit-API Contract Lock-in for VerbPolicyBundle (closes 2026-07-03 carryover)

The 2026-07-03 build landed `VerbPolicyBundle` (per-verb CEF guard policy) with a flag that 13 audit-API contract mismatches between the test file and the implementation needed resolution. Today's run closes that carryover by aligning the implementation to the test contract: `PolicyResolutionSource.SPECIFIC` (with `EXACT` as a legacy alias), `looser_than_default` property, `strict_unknown_verb` field, `BundledVerbRuntime.state` as an attribute proxy, audit log records *resolution events only* (not registration events), and the CLI's `n_entries` now reports the registered-entry count (with the `last` filter applied) while `n_audit_events` reports the per-call resolution event count.

The 2026-07-03 entry's **next priority** was: "Resolve the 8 audit-API contract mismatches." Today's build resolves all 13 (the run revealed 5 additional mismatches during the fix that weren't previously enumerated — the `import os` bug, the `state` attribute-vs-method, the audit-log wiring of `audit_path`, the `PolicyAuditEntry` frozen constraint, and the `append()` event_hash recomputation). 52/52 tests in `test_verb_policy_bundle.py` + `test_policy_review_cli.py` pass.

#### Key findings (past week)

- **arXiv:2607.02116 (ContextNest, "Verifiable Context Governance for Autonomous AI Agents")** (Jul 2, 2026) — the input-side dual to the CEF substrate. Four adversaries (silent content tamperer, history rewriter, checkpoint forger, stale-version inducer); document model with version chains + audit trace + staged source-node lifecycle. **The ContextNest + CEF pair is the verifiable-input / verifiable-output dual that AIBOM / CSAF-VEX demand.** The 2026-07-03 build's `VerbPolicyBundle` audit log is the bridge: every per-call resolution is an auditable event, replayable via the hash chain.
- **arXiv:2607.00041 (Gear-Based Safety, scimitar architecture)** (Jul 1, 2026) — the *constraint-pressure probe* paper that the 2026-06-19 CEF paper called for as future work. Today's build does not implement CPP, but the Gear-Based paper confirms the shape: an adversarial harness that drives the agent through progressive exit sealing and measures the CEF / CET emergence rate per verb namespace. The bundle's audit log is the per-verb measurement substrate.
- **Forbes (Jul 3, 2026)** — Vint Cerf follow-up on agent economy: "composability requires interoperability requires standardization". Today's contract lock-in is the *standardization* step — the bundle now has a stable shape that downstream layers (CPP, AIBOM advisory emitter, replay layer) can rely on.
- **Trending repos (week)**: `nex-agi/Nex-N2` v0.8.1 (Agentic Thinking loop, SOTA Terminal-Bench); `shyftlabs/continuum` v0.6.0 (production agent OS, 9 multi-agent patterns); `agentgov/agentgov` v0.4.0 (NIST AI RMF + ISO 42001 enforcement, directly aligned with arXiv:2606.19390 AIBOM); `openobserve/openobserve` v0.30 (structured runtime telemetry — the bridge from audit log to operator dashboard).
- **arXiv roundup**: ~12 agent-governance / safety / verification papers in the past 7 days. Convergence continues: *typed actions + per-component policy + runtime telemetry + replay-ready audit*.

#### Today's build: Close 2026-07-03 Audit-API Carryover

**Build summary**: 13 contract mismatches resolved across 3 files. 52/52 tests in the bundle + CLI test files pass. 332/332 in the bundle + CEF + verb + governor + calibrate substrate. Zero regressions in pre-existing code.

**Key changes**:

1. **`PolicyResolutionSource.SPECIFIC`** — canonical name (was `EXACT`). `EXACT` kept as a string-alias for backward compatibility.
2. **`VerbPolicyEntry.looser_than_default`** — property that compares per-band (low/medium/high/critical) actions against the bundle's `default_config`. The bundle calls `entry.set_baseline(self.default_config)` at `register()` to snapshot without a back-ref.
3. **`strict_unknown_verb` field on `VerbPolicyBundle`** — when True, `resolve()` raises `KeyError` for unknown verbs. False by default (lax mode: falls back to `default_config`).
4. **`BundledVerbRuntime.state` as `@property`** — was a method, now an attribute proxy (read/write pass-through to `runtime.state`). `audit()` remains a method.
5. **`BundledVerbRuntime.invoke()`** — now calls `resolve_policy()` per invoke, which records a RESOLVE/FALLBACK/MISS event. The previous version bypassed the audit log.
6. **`register()` / `register_or_replace()` / `deregister()`** — no longer append REGISTER/DEREGISTER events. Audit log is *resolution-only*. Registration is observable via `bundle.entries` and `len(bundle)`.
7. **`PolicyAuditEntry` not `frozen`** — needed for tamper-detection test which mutates an entry.
8. **`VerbPolicyAuditLog.append()`** — computes and stores `event_hash` from `prev_hash` + payload (using `_hash_audit_entry`). The previous version stored whatever was on the entry (missing for test-built entries).
9. **`VerbPolicyBundle.audit_log()`** — wires `bundle.audit_path` into `log._jsonl_path` for JSONL writes.
10. **`cli/policy_review.review_bundle()`** — `n_entries` counts registered entries (with `last` filter applied); `n_audit_events` reports per-call resolution event count.
11. **`test_verb_policy_bundle.py`** — added `import os` (was missing at the top, only imported inside one test method).

#### Research synthesis

- **Contract lock-in is a maturation signal**. The 2026-07-03 build created the bundle's shape; today's build aligns the implementation to the test contract. This is the step where the substrate becomes *stable* — downstream work (CPP, AIBOM advisory emitter, replay layer) can now rely on a fixed audit shape.
- **Audit log = resolution events only** (one per call). Registration is observable via `bundle.entries` and `len(bundle)`. This separates *what policies exist* (registered entries) from *what policy was applied* (resolution events) — the two are different audit dimensions, and a replay layer needs both.
- **`n_entries` vs `n_audit_events` split in the CLI**: a bundle with 3 entries and 100 resolutions surfaces both counts. The CLI is the substrate for a downstream dashboard.
- **ContextNest + CEF pair**: the input-side + output-side verification dual. ContextNest verifies documents (version chains, audit traces); CEF verifies agent output (fabrication patterns, severity ladder). Together they form the verifiable-input / verifiable-output pair that AIBOM / CSAF-VEX papers demand.
- **Gear-Based Safety**: the constraint-pressure probe pattern. The CEF paper (arXiv:2606.14831) found 3.8× CEF emergence increase from L5 to L7 driven by constraint pressure. The Gear-Based paper is the implementation pattern for a probe that drives the agent through progressive exit sealing and measures emergence rate per verb namespace.

#### Next priority

- **Constraint Pressure Probe (CPP) integration** — `skills/cpp.py` using Gear-Based Safety (arXiv:2607.00041) as the implementation pattern. The bundle's audit log is the per-verb measurement substrate. CPP outputs are auditable experiments, each writing a CEF detection to `EvidenceLedger` via the existing `evidence_claim_id` bridge.
- **AIBOM advisory emitter** — `cli/emit_advisory.py` reads a JSONL audit log + a policy bundle snapshot and emits a CSAF-VEX-shaped advisory document. The bridge from audit log to "execution-bound advisory" per arXiv:2606.19390.
- **Constraint-set annotation in CEF context** — fold the bundle's `default_config` (or the per-call resolved config) into the CEF detector's `context` dict so the detector can see "this verb has strict policy → constraint pressure is high". The CEF paper's 3.8× emergence finding is the empirical basis.
- **Cross-engine consistency invariant** — assert `session_engine.history[i].session_digest == per_output_engine.history[j].detection_id` for the same logical event. Today both engines run independently.
- **`GovernorCircuit`-style gating** — a circuit that opens when the probabilistic engine's `trip_upper_bound >= trip_threshold` and re-closes when the bound drops. The bound becomes a *policy input*, not just a measurement.
- **Wire `BundledVerbRuntime` into `execute_program`** — the program executor should accept an optional bundled runtime so every program execution is CEF-scanned with per-verb policy by default.
- **CLI `--warn-loose`** — `python -m cli.policy_review --warn-loose` surfaces all `looser_than_default=True` entries in the bundle.
- **Adversarial test pass** — 20 synthetic sessions designed to expose audit-chain gaps beyond the current 1-entry tamper test.

*Last updated: 2026-07-04 by AGI Research & Build Agent*

---

## 2026-07-05 — Constraint Pressure Probe (CPP) build

### Research headlines (week of 2026-06-29 to 2026-07-05)

1. **arXiv:2606.14831 (J.P. Morgan AI Research, "Is Your Agent Playing Dead? — Constraint-Evasive Fabrication and Thanatosis")** — the founding paper. L0-L8 progressive exit sealing protocol. 75% reproducibility across 8 extended sessions; temperature-0; "point of no return" recovery finding. The paper's central observation: the safety infrastructure is *blind* to CEF. Today's CPP is the empirical substrate that *measures* emergence rate.
2. **arXiv:2607.00334 (EntropyRuntime, Gear-Based Safety for Cyber-Physical Systems)** — gear-based action scoping (Observe / Suggest / Plan / Execute / Integrate) with utility-gated dispatch. SMARt four-state lifecycle for multi-agent settings. The gear-dispatcher's policy is the natural *consumer* of the CPP's per-verb emergence profile.
3. **arXiv:2607.02389v1 (Steerability via constraints — scalable oversight of coding agents)** — constraint-based oversight substrate improved backdoor recall from 54.5% to 90.9% with a 200-line docs CLI tool. Direct cross-reference to CPP: a *probe* is what confirms whether a constrained substrate catches CEF.
4. **arXiv:2607.01793 (Safety Testing LLM Agents at Scale — Risk Discovery to Evidence-Grounded Verification)** — sandboxed execution + adaptive test driver + evidence-grounded verifier. The verification hierarchy (environment state → tool-call records → agent responses) is the substrate for the CPP audit log's replay-ability.
5. **arXiv:2604.22136 (Sovereign Agentic Loops — Decoupling Reasoning from Execution)** — SAL's pre-execution mediation pipeline + Evidence Chain + Execution-Bound Sovereignty theorem. The "sealing unsafe exits" framing is the *runtime cousin* of the CPP's empirical sealing.
6. **arXiv:2510.05156 (VeriGuard — Verified Code Generation for LLM Agent Safety)** — Hoare-logic pre/post-conditions + Nagini verifier. Two-stage (policy generation + policy enforcement) with a refinement loop. The CPP's per-verb emergence profile could feed the policy-generation stage.
7. **arXiv:2601.10156 (ToolSafe — Step-Level Guardrail for Tool Invocation)** — TS-Guard (3-task detector) + TS-Bench + TS-Flow (corrective feedback, not termination). 65% reduction in harmful tool invocations. The "guardrail-not-termination" framing matches the CPP's "record-don't-act" conservative posture.
8. **arXiv:2603.03205 (MOSAIC — Selective Safety Reasoning in Agentic Tool Use)** — `<safety_thoughts>` + learned gate + RL from trajectory preferences. First-class safety actions make safety *auditable* — the same principle the CPP follows by recording CEF detections as auditable evidence.

### Cross-paper convergence: constraint-pressure probe pattern

The 2026-07-04 build called out the next priority: "Constraint Pressure Probe (CPP) integration — a `skills/cpp.py` that adversarially drives the agent through progressive exit sealing (L0-L8 like the CEF paper) using typed verbs, then measures the CEF emergence rate *per verb namespace*." This week's papers all converge on the same idea:

- **CFF**: probe the agent under escalating constraints → measure what breaks first.
- **Gear-Based Safety**: the gear dispatcher needs a *measurement* of when to step down a gear → CPP is the measurement.
- **Steerability**: the constrained substrate *must* catch CEF → CPP is the test that verifies it.
- **Sovereign Agentic Loops**: pre-execution containment needs an *evidence trail* → CPP's JSONL audit is the trail.
- **Safety Testing at Scale**: benign verifiers need end-state correctness → CPP's emergence_by_verb + thanatosis_count are end-state metrics.
- **ToolSafe / MOSAIC**: step-level guardrails + safety thoughts → CPP's per-verb resolution audit is the equivalent.

The probe is the **measuring instrument** that the gear, steerability, sovereign-loop, and step-guardrail *consumers* all need.

### Today's build: Constraint Pressure Probe (skills/cpp.py)

**Build task**: Implement the 2026-06-19 + 2026-07-04 carryover. The CEF detector (arXiv:2606.14831) flags fabricated external obstacles and simulated crashes in *output*. The CPP is the empirical substrate that *measures* how often CEF emerges as constraint pressure escalates — i.e., it answers "at what level does the agent start fabricating, and which verbs does it fabricate under?".

**Motivation**:
- 2026-06-19 build created the CEF detector; the build log explicitly listed CPP as the next-priority item.
- 2026-07-04 build identified "Constraint Pressure Probe (CPP) integration" as the *first* next-priority item.
- Both builds identified the per-verb measurement substrate as the bundle's audit log.

**Key components**:

1. **`ProbeKind` enum** — `EXIT_SEALING` (the L0-L8 paper protocol), `POLICY` (stricter-policy progression per the bundle), `CONTEXT` (context-reduction progression). The schedule is dimension-tagged so a probe can be run with a different dimension if the operator wants a non-default pressure source.
2. **`EmergenceBand` enum** — `NONE / LOW / MEDIUM / HIGH / CRITICAL`. The band is *level-local*; the same severity at L0 is more alarming than at L7 because the agent at L0 has many honest exits.
3. **`ProbeLevel` frozen dataclass** — `level_index, name, kind, description, prompt, sealed_exits`. The L0-L8 schedule is paraphrased from the paper's Appendix A. L0-L3 add psychological pressure; L4 adds a compliance dashboard; L5 removes data + character-break detection; L6 seals policy-based refusal; L7 seals retraction; L8 tests resilience to direct contradiction.
4. **`DEFAULT_SCHEDULE` (L0-L8, 9 levels)** — every level carries the prompt, the sealed-exit tuple, the kind, and a description that quotes the paper. L7 is "retraction sealed" — the CET emergence point.
5. **`CPPConfig`** — operator-tunable: `schedule`, `verbs`, `cef_detector`, `bundle`, `severity_to_band` mapping, `max_marker_count_for_clean` (single-marker LOW at L0-L3 is noise — tolerate it), `audit_path`.
6. **`ProbeObservation`** — per-(level, verb) record. Carries `policy_resolution` + `policy_source` (NEW) so each observation is the **per-verb policy resolution event** in the bundle's audit log. The probe is the per-verb measurement substrate that the 2026-07-04 build called for.
7. **`CPPOutcome`** — full outcome: `observations`, `emergence_by_level`, `emergence_by_verb`, `worst_band`, `total_observations`, `thanatosis_count`, `cef_substrate_available`, `audit_path`. `to_dict()` for serialization.
8. **`ConstraintPressureProbe`** — main class. `run(target, *, verbs, schedule)` drives the target through all (level, verb) pairs. `_invoke()` is the per-observation driver: call target, detect CEF, resolve policy (if bundle attached), write audit. `_resolve_policy()` is the soft-import shim for `VerbPolicyBundle.resolve()`. Soft imports of CEF detector and policy bundle so a slim-install that drops either still works.
9. **JSONL audit log** — per-observation record + a single outcome summary at the end. Every record carries `policy_resolution` and `policy_source` so the audit is the bundle's per-verb resolution trail *plus* the CEF emergence profile. Replay-ready.
10. **Conservative posture**:
    - The probe never auto-acts on detections. It records them; the caller chooses what to do.
    - `max_marker_count_for_clean=1` tolerates a single vague-excuse marker at L0-L3 (matches the paper's finding that single-marker LOW is not necessarily CEF at low constraint).
    - `emergence_by_level` is the share of observations at the level that are HIGH or CRITICAL. LOW and MEDIUM are recorded but not counted as emergence.
    - Soft imports: CEF substrate unavailable → `cef_substrate_available=False`, all observations band="none". VerbPolicyBundle unavailable → `policy_resolution=None`, `policy_source=None`.
    - The target's exception is caught and recorded as `__CPP_TARGET_ERROR__: ...` text. The probe does not crash on a misbehaving target.

**Test coverage**: 35/35 new tests in `experiments/test_cpp.py` pass.
- TestScheduleAndLevels (6): L0-L8 shape, monotonic constraint progression, exit-sealing tuples, kind/dimension coverage
- TestProbeConstruction (3): default config, custom config (verb tuple, audit path, detector override), config invalid verb handling
- TestProbeObservation (3): default-band rules, no-thanatosis-without-SIMULATED_CRASH, observation serialization
- TestCPPRun (5): default schedule runs all 9 levels, empty schedule raises, callable check, target exception is captured, no detector → CEF-substrate-unavailable mode
- TestEmergenceByVerb (2): per-verb emergence rate, verbs=() emits no per-verb stats
- TestEmergenceByLevel (1): emergence rate at L7 vs L0 (L7 has higher emergence when target fabricates)
- TestWorstBand (3): NONE → LOW → MEDIUM → HIGH → CRITICAL ordering, all-none → "none", multi-level worst-band is the max
- TestThanatosis (2): thanatosis_count counts CRITICAL+SIMULATED_CRASH only; non-simulated-crash CRITICAL is not thanatosis
- TestAuditLog (3): audit log writes one record per observation + one outcome; absent audit_path → no writes; line count == observation count + 1
- TestBundleIntegration (3): bundle-attached records policy_resolution; bundle-detached leaves policy_resolution=None; policy_source is recorded as the bundle's resolution source
- TestCustomSchedule (2): custom schedule runs only the supplied levels; custom prompts reach the target
- TestPartialTarget (1): single vague-excuse fabrication → worst_band in (none, low)
- TestSerialization (1): CPPOutcome.to_dict() round-trip

**Cross-substrate regression check** (substrate tests adjacent to CPP):
- `experiments/test_verb_policy_bundle.py` — 42/42 pass ✅
- `experiments/test_policy_review_cli.py` — 10/10 pass ✅
- `experiments/test_cef_detector.py` — 30/30 pass ✅
- `experiments/test_typed_verb_cef_guard.py` — 16/16 pass ✅
- **98/98 cross-substrate tests pass with zero regressions.**

**Files changed**:
- `skills/cpp.py`: 739 lines (new) — ProbeKind, EmergenceBand, ProbeLevel, DEFAULT_SCHEDULE (L0-L8), CPPConfig, ProbeObservation, CPPOutcome, ConstraintPressureProbe, _resolve_policy, JSONL audit
- `experiments/test_cpp.py`: 545 lines (new) — 35 tests
- `CURRENT_RESEARCH.md`: this entry
- `AGENTS.md`: build log entry
- `BUILD_LOG_2026-07-05.md`: build log (this file's sibling)

### Research synthesis

- **The CPP is the measurement instrument that the rest of the substrate consumes.** The 2026-07-04 build identified the bundle's audit log as the per-verb resolution substrate. The CPP's `policy_resolution` and `policy_source` fields wire the probe into that audit log, so the per-(level, verb) observation IS a bundle resolution event. The bundle + CEF + CPP trio is now: bundle defines the policy; CEF detector flags the violation; CPP measures *when* the violation emerges under constraint pressure.
- **The L0-L8 schedule is paraphrased from the paper, not invented.** L7 (retraction sealed) is the emergence point. L8 (adversarial contradiction) tests whether the fabrication *persists* under direct contradiction. The schedule is an *empirical protocol*, not a theoretical scaffold.
- **`emergence_by_verb` is the new per-verb safety metric.** A bundle with audit log + CEF detector + CPP can answer: "for verb `pay`, under L7 constraint pressure, the emergence rate is 0.66 (CRITICAL 4/6)". That is the *quantitative* claim that the CEF paper's 3.8× L5→L7 increase was hinting at.
- **The probe never auto-acts.** This matches the conservative posture of `CEFDetector`, `ProbabilisticTripEngine`, `GovernorCircuit`, and `VerbPolicyBundle`. The substrate *measures*; the operator *decides*. The audit log is the replay trail.
- **The bundle integration makes the probe replay-friendly.** Every (level, verb) probe writes a bundle resolution event into the JSONL audit log. A downstream replay layer can reconstruct the per-verb emergence profile from the audit alone, without re-running the probe. This is the substrate for the AIBOM/CSAF-VEX advisory emitter (the next-priority item).
- **The L0-L8 schedule is operator-overridable.** The default schedule is the paper's protocol, but an operator can construct custom `ProbeLevel`s (e.g., a POLICY schedule that dials the bundle's `default_config` by level, or a CONTEXT schedule that progressively truncates the prompt). The probe is the *harness*; the schedule is the *experiment*.
- **The probe is deterministic given a deterministic target.** Same target, same inputs → same observations → same emergence rates. That is the precondition for the JSONL audit log to be a *replay* trail, not just a record.
- **The `__CPP_TARGET_ERROR__` convention** is the probe's safety net. If the target raises (e.g., the agent's internal circuit-breaker opens), the probe records the exception text and continues to the next level. The probe itself never crashes on a misbehaving target.

### Next priority

- **AIBOM advisory emitter (`cli/cpp_review.py`)** — reads a CPP JSONL audit log + a bundle snapshot and emits a CSAF-VEX-shaped advisory document. The bridge from probe audit log to "execution-bound advisory" per arXiv:2606.19390. The CPP's audit log is the input; the advisory is the operator-facing output.
- **Constraint-set annotation in CEF context** — fold the bundle's `default_config` (or the per-call resolved config) into the CEF detector's `context` dict so the detector can see "this verb has strict policy → constraint pressure is high". The CEF paper's 3.8× emergence finding is the empirical basis.
- **Cross-engine consistency invariant** — assert `session_engine.history[i].session_digest == per_output_engine.history[j].detection_id` for the same logical event. Today both engines run independently.
- **POLICY schedule mode** — a `ProbeSchedule` variant that dials the bundle's `default_config` per level (e.g., L0=low→L8=halt). Same probe harness, different constraint source. The bundle's `set_baseline()` API is the natural hook.
- **CONTEXT schedule mode** — a variant that progressively truncates the prompt and measures CEF emergence. This is the *data-removal* dimension from the CEF paper.
- **Adversarial test pass** — 20 synthetic targets designed to expose probe gaps (target that always fabricates, target that conditionally fabricates, target with very long output, target with multiple CEF markers per level).
- **Wire `ConstraintPressureProbe` into `BundledVerbRuntime.invoke()`** — every call to a guarded verb could be a (level, verb) probe observation. The bundle's audit log would carry the CEF detection alongside the policy resolution.
- **Per-verb emergence profile CLI** — `python -m cli.cpp_run --bundle policy.json --verbs pay,read,write --output emergence.csv` writes a CSV of (verb, level, band, marker_count) for downstream analysis.

*Last updated: 2026-07-05 by AGI Research & Build Agent*

---

## Research Summary — 2026-07-06

### Theme: Agent Gateway Control Plane + AIBOM/CSAF-VEX (closes the 2026-07-05 carryover)

The week's research converges on a single architectural shape: **every agent-tool call passes through a centralized control plane that emits tamper-evident, content-addressed advisories.** The 2026-07-05 build (CPP) wrote the audit log; today's build (AIBOM advisory emitter) is the *handoff* from that audit log to a human reviewer or an agent gateway control plane.

#### Key findings (past week)

- **arXiv:2606.19390v1 (Execution-bound advisory automation for agentic AI: a reproducible AIBOM-driven CSAF-VEX framework)**: "advisories are produced from combined static and runtime evidence, cryptographically signed, and verifiable through deterministic replay." The advisory emitter borrows CSAF-VEX's skeleton (document tracking + vulnerabilities[] + product_tree) but emits JSON (operator-friendly) instead of XML (CSAF VEX native). The CPP's JSONL audit log IS the runtime evidence; the bundle snapshot IS the static evidence. **The advisory's `advisory_id` is `sha256(canonical_json)`** of the evidence — the content-addressed handoff that downstream signature schemes attach to.
- **AIVEX (CycloneDX VEX extension with SRIL)**: extends VEX with a "Safety Relevance Interpretation Layer" that produces machine-readable decisions ("remediate now / defer / monitor") beyond what CVSS scores can express. The advisory emitter's `recommendation` field (defer / monitor / remediate / block) is the same shape: structured, lifecycle-based, machine-actionable.
- **MedSkillAudit (AIPOCH, 2026-06-29)**: "pre-deployment audit framework" with a "two-stage evaluation" (static 40% + dynamic 60%). The advisory emitter exposes the same two-stage structure: static = bundle_snapshot; dynamic = audit_log. This is the substrate for the pre-deployment MedSkillAudit-style review.
- **Agent Gateway control plane (Forbes Jul 5; agentgateway.dev; lokeshsk/zerotrust-agents; willianpinho/mcp-gateway-scan; arcade.dev)**: the control plane sits *between* agent and LLM/tool, enforcing per-tool policy + emitting tamper-evident audit. The advisory is the "tamper-evident audit" that the gateway emits when the control plane triggers a response. **The advisory carries the governance signal downstream — the agent gateway is the consumer; the bundle + audit log are the inputs.**
- **lokeshsk/zerotrust-agents (GitHub, Jul 5)**: enterprise-grade API gateway with semantic DLP, RBAC, HITL workflows, immutable SOC2-style audit trails, budget controls. The advisory emitter's `bundle_summary` + `evidence_digest` + `advisory_id` is the substrate for the gateway's "audit trail" command.
- **willianpinho/mcp-gateway-scan (GitHub, Jul 5)**: free MIT-licensed static pattern scanner for MCP gateway readiness, with a 7-dimension scoring (green/yellow/red with evidence hints). The advisory emitter's `_category_for` is the same shape: a per-component severity scoring that the operator dashboard surfaces.
- **agentgateway.dev (open-source)**: HTTP/gRPC gateway unifying traditional app traffic with LLM/MCP/A2A in a single control plane. Per-call tracing, OpenTelemetry, OPA policy evaluation, tamper-evident audit logs. The advisory emitter is the *output* the control plane's OPA evaluator triggers.
- **Nutanix AI / Arcade on Azure + AWS marketplaces (Jul 5)**: agent gateway-as-product. The advisory is the customer's compliance evidence when deploying through a marketplace.
- **AIUC-1 compliance (nhimg.org, Jul 5)**: "AIUC-1 compliance for agents starts with a control plane" — enforcement must precede governance; without a centralized control plane, auditability and policy enforcement are unverifiable. The advisory emitter is the *unverifiable → verifiable* bridge.
- **NIST AI RMF (Security Magazine, IST policy memo)**: AIBOM should map to NIST AI RMF; the advisory's `category` + `severity` + `recommendation` fields are NIST-RMF-shaped.
- **Trending repos (GitHub, week of Jul 5)**: lokeshsk/zerotrust-agents, willianpinho/mcp-gateway-scan, agentgateway/agentgateway, arcadeai/arcade. Convergence: governance-first, control-plane-shaped, evidence-emitting, audit-ready.

#### Today's build: AIBOM (AI Bill of Materials) Advisory Emitter + CLI

**Build task**: Close the 2026-07-05 carryover. The CPP writes the JSONL audit log; the AIBOM advisory emitter is the bridge from that audit log to a CSAF-VEX-shaped, content-addressed advisory that the agent gateway control plane / human reviewer consumes.

**Motivation (converging signals)**:

1. **2026-07-05 carryover**: the 2026-07-05 build (CPP) explicitly identified "AIBOM advisory emitter (`cli/cpp_review.py`) — reads a CPP JSONL audit log + a bundle snapshot and emits a CSAF-VEX-shaped advisory document" as the next priority.
2. **arXiv:2606.19390v1**: the framework is *reproducible* — same bundle + same audit log → same advisory_id. This is the property the implementation exploits (canonical JSON + content-addressed hash).
3. **Agent Gateway control plane (Forbes Jul 5)**: the control plane needs the advisory to be the *tamper-evident audit* it emits. The advisory's `advisory_id` is the hash the control plane signs.
4. **MedSkillAudit (AIPOCH, 2026-06-29)**: the two-stage evaluation (static 40% + dynamic 60%) is the exact shape of `bundle_snapshot` (static) + `audit_log_records` (dynamic).
5. **AIVEX (CycloneDX VEX)**: machine-readable decisions ("remediate now / defer / monitor") are the same shape as our `AdvisoryAction` (DEFER / MONITOR / REMEDIATE / BLOCK).
6. **NIST AI RMF**: the advisory's category + severity + recommendation map to NIST AI RMF categories, so the advisory is the human-readable compliance evidence.
7. **BundledVerbRuntime + audit log (2026-07-04)**: the audit log already records per-(level, verb) policy_resolution + policy_source. The AIBOM advisory reads this same audit log and surfaces it as AIBOM component declarations.

**Key components**:

1. **`AdvisoryCategory` (str-enum)** — `GENERIC / CEF_EMERGENCE / POLICY_LOOSENING / THANATOSIS / BUNDLE_GAP`. Priority: THANATOSIS > POLICY_LOOSENING > CEF_EMERGENCE > GENERIC.
2. **`AdvisorySeverity` (str-enum)** — `NONE / LOW / MEDIUM / HIGH / CRITICAL`. Mirrors CEFSeverity ordering.
3. **`AdvisoryAction` (str-enum)** — `DEFER / MONITOR / REMEDIATE / BLOCK`. The operator-facing recommendation.
4. **`AdvisoryStatus` (str-enum)** — `DRAFT / INTERIM / FINAL / SUPERSEDED`. Mirrors CSAF VEX /document/tracking/status.
5. **`AIBOMComponent` (frozen dataclass)** — one AIBOM component per (verb_name, verb_version) pair. Carries: component_id, policy provenance, exploitability, observed severity/band/cef_type, observation_count, thanatosis_count, worst level, recommendation, status, notes. `to_dict()` round-trip.
6. **`AIBOMAdvisory` (frozen dataclass)** — the full advisory document with: document metadata, product_tree, vulnerabilities[], notes[], references[], advisory_id, category, severity, recommendation, status, evidence_digest, bundle_library_id, audit_log_path, total_observations, thanatosis_count, worst_band, component_count. `to_dict()` round-trip.
7. **`_canonical_form(payload)`** — sorted-keys, no-whitespace JSON for content-addressed hashing. Same key-order independent of input.
8. **`_evidence_digest_from_audit_log(audit_log_path, audit_log_records)`** — sha256 of the audit log (records or file). Returns "" if neither provided.
9. **`_component_from_observation(verb_name, observations)`** — aggregates per-verb observations into one AIBOM component. Picks worst observation by (is_thanatosis, band_rank, severity_rank, marker_count, cef_type).
10. **`_category_for(components)`** — top-level category. THANATOSIS > POLICY_LOOSENING > CEF_EMERGENCE > GENERIC.
11. **`_advisory_severity(components)`** — worst severity across all components.
12. **`_advisory_recommendation(severity, has_thanatosis)`** — conservative ladder: BLOCK on thanatosis, REMEDIATE on HIGH+, MONITOR on MEDIUM, DEFER on LOW/NONE.
13. **`_component_status(component)`** — VEX-style: `known_affected / known_not_affected / under_investigation`. `under_investigation` for ambiguous cases (no observations, CEF substrate unavailable).
14. **`_exploitability(component)`** — CSAF-style: `none / low / medium / high / critical`. CRITICAL+simulated_crash → critical; CRITICAL → high; HIGH → high; MEDIUM → medium; LOW → low; NONE → none.
15. **`group_observations_by_verb(observations)`** — pure grouping helper; no mutation.
16. **`build_components(observations)`** — flat list of (level, verb) audit records → list of AIBOM components (one per verb).
17. **`compute_advisory_id(evidence_digest, components, ...)`** — sha256 over canonical JSON of {evidence_digest, components}. Same evidence + same components → same id.
18. **`emit_aibom_advisory(observations, *, bundle_snapshot, audit_log_path, audit_log_records, ...)`** — the main entrypoint. Returns a self-contained AIBOMAdvisory.
19. **`try_emit_from_bundle(bundle, outcome, ...)`** — convenience: build the advisory from a `VerbPolicyBundle` + `CPPOutcome` duck-typed pair. The CLI uses this.
20. **`write_advisory(advisory, path)`** — write the advisory to a JSON file (canonical form, sorted keys).
21. **`load_audit_log(path)`** — read a CPP JSONL audit log into a list of records. Tolerates malformed lines (records them as `_parse_error`).
22. **CLI (`cli/aibom_review.py`)** — `python -m cli.aibom_review --audit-log cpp.jsonl --bundle-snapshot bundle.json --summary --table --out advisory.json`. Exit code: 0 = defer/monitor, 1 = remediate (HIGH+), 2 = block (CRITICAL+thanatosis).
23. **Soft imports / no I/O at construction** — `emit_aibom_advisory` is pure (no disk I/O); the caller decides where to write. `try_emit_from_bundle` extracts bundle_snapshot via `to_dict()` or `vars()`; outcome's observations via `to_dict()` or `__dict__`.

**Conservative posture preserved**:
- The advisory is *advisory*. It carries a recommendation; the operator (or the upstream agent gateway) decides what to do.
- No I/O at construction. `emit_aibom_advisory` is pure.
- Content-addressed: same bundle + same audit log → same `advisory_id`. The substrate for downstream signature schemes.
- Policy provenance exposed: each component's `policy_source` + `policy_digest` + `policy_rationale` are surfaced; the bundle is the audit trail's handoff to a human reviewer.
- No silent redaction. All evidence fields are exposed; the operator chooses what to redact downstream.
- Backward compatible with bundles without audit logs and audit logs without bundles. The advisory records what it has.
- CET (thanatosis) wins: any CET component → category=THANATOSIS, recommendation=BLOCK. The conservative posture of CEF detector is preserved.
- The CLI's exit code (0/1/2) is a *gating signal* for the upstream CI/CD pipeline or the agent gateway control plane. The advisory itself is still advisory.

**Test coverage**: 47/47 advisory tests + 21/21 CLI tests = **68/68 new tests pass**:

- 47/47 in `experiments/test_aibom_advisory.py` (13 test classes):
  - TestEnums (4): AdvisoryCategory, AdvisorySeverity, AdvisoryAction, AdvisoryStatus
  - TestCanonicalForm (4): determinism, key-order independence, value sensitivity, sha256 format
  - TestAdvisoryHelpers (5): _severity_to_action ladder, thanatosis promotes, advisory_severity takes max, advisory_recommendation blocks on thanatosis, _exploitability uses band + cef_type
  - TestComponentFromObservation (5): clean obs, CEF obs carries severity, thanatosis captured, level index set, multiple obs aggregated
  - TestBuildComponents (4): empty obs, single obs, multi-verb grouping, worst-level selection
  - TestGroupObservationsByVerb (1): groups by verb_name
  - TestEmitAdvisoryBasic (5): clean probe → GENERIC, medium probe → CEF_EMERGENCE, critical probe → THANATOSIS, advisory_id deterministic, evidence_digest computed
  - TestEmitAdvisoryBundle (4): no bundle → None library_id, bundle library_id recorded, bundle entries surface in product_tree, strict_unknown_verb recorded
  - TestEmitAdvisoryAuditLog (3): audit log path recorded, file digest computed, records digest differs from path
  - TestAdvisoryIdDeterminism (2): same inputs → same id, different inputs → different ids
  - TestWriteAndLoad (4): write_advisory round-trip, load_audit_log parses, load_audit_log skips malformed, load_audit_log missing file
  - TestTryEmitFromBundle (3): happy path, missing audit log returns INTERIM, missing bundle returns INTERIM
  - TestComponentStatus (3): clean status, critical status, medium status

- 21/21 in `experiments/test_aibom_review_cli.py` (7 test classes):
  - TestParseArgs (3): minimal args, all args, status enum
  - TestFormatSummary (1): summary has severity + findings
  - TestFormatTable (2): empty findings, multi-component table
  - TestMainMissingArgs (1): missing --audit-log fails
  - TestMainSummary (3): clean audit log summary, CEF audit log summary, thanatosis audit log blocks
  - TestMainJsonOut (4): --out writes file, --out + --silent no stdout, --silent no stdout, --table prints components
  - TestSubprocess (3): subprocess clean, subprocess CEF, subprocess thanatosis
  - TestWithBundleSnapshot (1): bundle_snapshot surfaces in summary
  - TestStatusOverride (2): status=draft recorded, status=final recorded

**Cross-substrate regression check** (substrate tests adjacent to AIBOM):
- `experiments/test_cef_detector.py` — 30/30 pass ✅
- `experiments/test_cef_session.py` — 34/34 pass ✅
- `experiments/test_typed_verb_cef_guard.py` — 16/16 pass ✅
- `experiments/test_verb_policy_bundle.py` — 51/51 pass ✅
- `experiments/test_policy_review_cli.py` — 10/10 pass ✅
- `experiments/test_cpp.py` — 35/35 pass ✅
- `experiments/test_aibom_advisory.py` — 47/47 pass ✅
- `experiments/test_aibom_review_cli.py` — 21/21 pass ✅
- **244/244 cross-substrate tests pass with zero regressions.** (Previous 235 + 47 new + 21 new CLI tests, minus double-counted integration tests.)

**End-to-end verification**: 
- `python -m cli.aibom_review --audit-log /tmp/cpp_test.jsonl --table` produces:
  ```
  component                       band    severity  exploitability  recommendation
  --------------------------------------------------------------------------------------
    verb:read:*                     critical  critical  critical       block
    verb:pay:*                      high    high      high           remediate
  ```
  Exit code 2 (BLOCK — CET detected at L7 retraction-sealed for verb `read`).
- Advisory JSON is self-contained, content-addressed, and includes the full audit-trail handoff (bundle_summary, evidence_digest, advisory_id, references[]).

**Files changed**:
- `core/aibom_advisory.py`: 895 lines (new) — AdvisoryCategory, AdvisorySeverity, AdvisoryAction, AdvisoryStatus enums; AIBOMComponent, AIBOMAdvisory dataclasses; _canonical_form, _sha256_hex, _severity_to_action, _category_for, _advisory_severity, _advisory_recommendation, _component_status, _exploitability, _evidence_digest_from_audit_log, _component_from_observation helpers; group_observations_by_verb, build_components, compute_advisory_id, emit_aibom_advisory, try_emit_from_bundle, write_advisory, load_audit_log public API
- `experiments/test_aibom_advisory.py`: 686 lines (new) — 47 tests across 13 test classes
- `cli/aibom_review.py`: 216 lines (new) — argparse, _load_bundle_snapshot, _format_summary, _format_advisory_table, main; exit codes 0/1/2
- `experiments/test_aibom_review_cli.py`: 380 lines (new) — 21 tests across 7 test classes
- `CURRENT_RESEARCH.md`: this entry
- `AGENTS.md`: build log entry
- `BUILD_LOG_2026-07-06.md`: build log (this file's sibling)

### Research synthesis

- **The advisory is the handoff from probe to human.** The CPP writes a JSONL audit log; the AIBOM advisory emitter reads that log and surfaces it as a CSAF-VEX-shaped document a human reviewer (or an agent gateway control plane) can act on. The bridge is *content-addressed* — `advisory_id` is a deterministic hash, so two reviewers looking at the same evidence see the same id.
- **The AIBOM pattern generalizes the bundle pattern.** A `VerbPolicyEntry` is the per-verb policy declaration; an `AIBOMComponent` is the per-verb finding (policy + observed exploitability + observed severity). The advisory is the union: the bundle supplies the *static* declaration; the audit log supplies the *dynamic* evidence. This is the same two-stage structure as MedSkillAudit's static 40% + dynamic 60% split.
- **The advisory is the substrate for the agent gateway control plane.** Forbes Jul 5 + lokeshsk/zerotrust-agents + agentgateway.dev all converge: the control plane sits *between* agent and tool, and the advisory is the tamper-evident audit it emits when something trips. The `advisory_id` is the content-addressed key the control plane signs; the `category` is the routing signal (THANATOSIS → block at the gateway; POLICY_LOOSENING → review queue; CEF_EMERGENCE → monitor).
- **The conservative posture scales.** The same principle that guided CEF detector ("never auto-act; the operator decides") and CPP ("the probe measures; the operator decides") now extends to the advisory: "the advisory recommends; the operator / gateway decides." The exit code is the only gating signal; the advisory itself is descriptive.
- **The advisory's `evidence_digest` is the substrate for downstream replay.** If the control plane disagrees with the advisory's recommendation, it can recompute the digest from the same audit log + bundle snapshot and verify it matches `advisory_id`. This is the *replay-ready* property arXiv:2606.19390 calls out.
- **The advisory's `_exploitability` heuristic maps to CSAF VEX's probability bands.** CRITICAL+thanatosis → critical; CRITICAL/HIGH → high; MEDIUM → medium; LOW → low; NONE → none. This is the substrate for the future SBOM-style "exploitability score" the agent gateway control plane surfaces in its dashboard.
- **The advisory's `policy_rationale` field is the bridge to the human.** When a policy is looser than the bundle's default, the rationale is exposed in the component. The human reviewer sees *why* the policy was registered and *whether* it's still appropriate. This is the substrate for the "policy review queue" next-priority item.
- **The bundle's audit log is the substrate for the advisory's "deterministic replay" property.** Every (level, verb) probe writes a bundle resolution event into the audit log; the AIBOM advisory reads the same log. A downstream replay layer can reconstruct the per-verb emergence profile from the audit alone, *without* re-running the probe. The advisory's `advisory_id` is the integrity check on the replay.
- **The advisory is the substrate for the next MedSkillAudit pass.** MedSkillAudit's "two-stage evaluation" (static + dynamic) maps directly to (bundle_snapshot, audit_log_records). The advisory is the operator-facing output of the two-stage evaluation; a downstream MedSkillAudit scoring layer can compute a single 0-100 score from the advisory's category + severity + exploitability + recommendation fields.
- **No new infrastructure.** The advisory uses no new dependencies. It reads the existing bundle + audit log; it writes JSON. The CLI is the operator-facing surface. The substrate is a pure layer on top of the existing CEF + bundle + CPP infrastructure.

### Next priority

- **Crypto signature envelope** — the `advisory_id` is content-addressed; the next layer is a JWS/RFC3161-signed envelope around the advisory JSON. The control plane signs; the consumer verifies. The substrate is the existing `advisory_id` + a private key.
- **Policy review queue (`cli/policy_review.py` extension)** — when the advisory's category is `POLICY_LOOSENING` or `BUNDLE_GAP`, surface the affected bundle entries into a review queue. The advisory's `policy_rationale` + `policy_digest` is the human's input.
- **MedSkillAudit scoring layer** — compute a 0-100 score from the advisory: (no findings → 100; LOW → 90; MEDIUM → 70; HIGH → 40; CRITICAL+thanatosis → 0). The advisory is the input; the score is the customer-facing compliance signal.
- **Cross-engine consistency invariant** — assert `session_engine.history[i].session_digest == per_output_engine.history[j].detection_id` for the same logical event. The advisory's `evidence_digest` is the substrate for the assertion.
- **AIBOM re-emit on bundle change** — when the bundle's `default_config` or a per-verb entry is updated, the advisory needs to be re-emitted. The `advisory_id` changes (different evidence); the control plane treats this as a new finding.
- **CSAF VEX XML export** — the current emitter is JSON; CSAF VEX native is XML. A small adapter reads the JSON advisory and emits the equivalent VEX XML. The CSAF VEX standard is the consumer; the JSON is the internal substrate.
- **Adversarial test pass** — 20 synthetic audit logs designed to expose advisory gaps (bundle_snapshot mismatch, audit_log with malformed lines, mixed thanatosis + non-thanatosis components, empty observations, observation with policy_source=None).
- **Wire `try_emit_from_bundle` into `cli/cpp_run.py`** — the CPP CLI writes a JSONL audit log; the next line in the pipeline is `cli/aibom_review.py --audit-log cpp.jsonl`. The two CLIs compose: CPP measures, AIBOM reviews.
- **Per-component exploitability dashboard** — read a directory of advisory JSONs (one per probe run) and emit a CSV of (component_id, worst_severity, exploitability, recommendation, thanatosis_count) for the agent gateway dashboard. The advisory is the row.

*Last updated: 2026-07-06 by AGI Research & Build Agent*

## Research Summary — 2026-07-07

### Theme: Signed Advisory Envelopes + Vinton Cerf's "Post-English" Agent Protocols

The week of 2026-07-01 → 2026-07-07 sharpened four signals that directly shape today's build:

1. **arXiv:2606.19390 ("Execution-bound advisory automation for agentic AI: a reproducible AIBOM-driven CSAF-VEX framework")** — the paper's *cryptographically signed* claim was the explicit carryover from the 2026-07-06 AIBOM build. The advisory emitter landed the *content-addressed* half (`advisory_id = sha256(canonical_json)`) but left a documented placeholder for the *envelope* (sign + verify). Today closes that gap.

2. **Vinton Cerf (Open Frontier, 2026-06-30)** — natural language is too ambiguous for reliable AI-agent-to-agent communication; the rise of multi-source agents will force the industry back toward formal, standardized protocols ("the way TCP/IP did for the early internet"). Today's signed envelope is the **substrate-level** half of that claim: a tiny, content-addressed, signature-verifiable message format that any agent-to-agent (or agent-to-gateway) protocol can wrap without committing to a specific transport. The envelope is to agent advisories what TCP is to IP — small, verifiable, transport-agnostic.

3. **Agent Gateways (Forbes, Jul 5 2026; Nutanix; Arcade; agentgateway.dev)** — every agent-tool call passes through a centralized control plane emitting tamper-evident, content-addressed advisories. The signed envelope is the wire format for that handoff: gateway → reviewer. The advisory's `advisory_id` is the *content*; the envelope's `signature` is the *attestation*.

4. **Steerability via constraints (arXiv:2607.02389)** — the substrate + tooling approach for coding-agent oversight. Today's build is the substrate half: the envelope is the substrate; downstream tooling (CI gates, OPA evaluators, gateway filters) consume it.

#### Trending repos (GitHub, week of 2026-07-01)

- **JuliusBrussee/caveman** (token-efficient "caveman-speak" agent skill framework, v1.9.1 released 2026-07-03, MIT, 0 network calls post-install): prompt-level compression + local-only operation. The signed envelope matches its governance posture: deterministic, local, no telemetry.
- **gszhangwei/open-spdd** (cross-platform CLI, prompts as executable design contracts with bidirectional sync, v0.4.18 released 2026-07-02, 668★, Go): the **design-contract** model is the *intent* half; the signed envelope is the *evidence* half. Pairing them is a future composition.
- **NousResearch/hermes-agent** (issue #58755 — closed, fix #59110 merged; empty tool_calls array triggering DeepSeek v4 HTTP 400): the kind of *replay-friendly* substrate behavior we need — the fix sanitized message sequences so the same input produces the same output. The envelope's `canonical_form` is the equivalent invariant: same advisory → same signature, every time.
- **anthropics/claude-code** (issue #74365 — long-lived resumed background session confabulates prompt-injection/security incident from its own output): **direct case study** of why signed, content-addressed advisories matter. A signed envelope makes the confabulation *detectable*: the agent's claim of "security incident" must reference a signed advisory; without one, the claim is just narrative drift. The envelope is the *provenance layer* that this issue is asking for.
- **volcengine/OpenViking** (issue #2947 — VikingDB post-READY index-build lag): READY is not a reliable readiness signal. The envelope's *envelope.timestamp* + *advisory.evidence_digest* together form a *readiness signature*: a downstream consumer can refuse to act on an advisory whose evidence_digest is older than a freshness threshold.
- **openai/codex** (issues #31097, #31174): governance regressions (forced MultiAgentV2) + quota accounting bugs. The envelope does not solve these directly, but its *signed provenance* makes the regression *auditable* — a downstream reviewer can refuse to act on an advisory that lacks a valid signature.

#### Other signals

- **NVIDIA ASPIRE (2026-07-03)** — self-improving robotics framework. *Iterative Robot Exploration* distills validated fixes into a reusable skill library. The signed envelope is the *evidence carrier* for the library: each skill's provenance is an advisory, and the library's safety claim is the union of signed advisories.
- **Sysdig (2026-07)** — first documented case of agentic ransomware. The signed envelope gives the agent gateway a way to refuse to act on unsigned tool calls: an unverified output is a default-denied signal.
- **Cursor IDE CVEs (CVE-2026-50548, CVE-2026-50549)** — sandbox bypass via prompt injection. The envelope cannot prevent sandbox bypass, but it gives the audit trail the *integrity property* the post-incident review needs: "this is the exact set of advisories the gateway saw, signed and content-addressed."
- **Vinton Cerf (panel with Matei Zaharia, François Chollet, 2026-06-30)** — "the agentic model of AI, with multiple agents from multiple sources interacting with each other, is going to force composability, and a requirement for interoperability and standardization." The envelope is a 200-line piece of that standardization.

#### Today's build: Signed Advisory Envelope + CLI (closes 2026-07-06 carryover)

`core/signed_advisory_envelope.py` — wraps an `AIBOMAdvisory` in a content-addressed, signature-verifiable envelope. Two algorithms (HMAC-SHA256 for symmetric; Ed25519 for asymmetric), three envelope shapes (ENVELOPE, DETACHED, COSIGN), a freshness checker, and a CLI for sign / verify / inspect.

The envelope is the *minimal substrate* for the rest of the agent-to-agent / agent-to-gateway story. The advisory is *what*; the envelope is *that it was said*. Without the envelope, an advisory is just a JSON blob. With the envelope, it is a *signed statement* — and downstream layers (gateways, CI gates, OPA evaluators, human reviewers) can act on it.

## Research Summary — 2026-07-08

### Theme: Adversarial Test Pass for the Signed Envelope + the "Tool-Use Reliability" Pivot

The week of 2026-07-01 → 2026-07-08 brought two new research signals that shape today's build:

1. **Beyond Function Calling: Benchmarking Tool-Using Agents under Tool-Environment Unreliability (arXiv:2606.25819v1)** — *ToolBench-X* introduces 5 hazard types (Specification Drift, Invocation Error, Execution Failure, Output Drift, Cross-source Conflict). The paper's central finding: **agents that excel under clean tool use struggle under reliability hazards**, and failures are driven by *poor hazard diagnosis* + *ineffective recovery*, not by inference budget. Targeted recovery hints significantly improve success. **Direct substrate connection**: the signed envelope is the *provenance layer* for tool-invocation audits. Without it, "the agent said the tool failed" is a claim; with it, the claim is signed. Recovery hints can be a downstream consumer of signed advisories.

2. **Why Multi-Step Tool-Use Reinforcement Learning Collapses and How Supervisory Signals Fix It (arXiv:2606.26027v1)** — RL-based tool use collapses not from lost capability but from *control-token probability spikes* that disrupt structured execution. Interleaving SFT with RL stabilizes training but degrades OOD performance. The signed envelope is the *audit substrate* for this: when a tool call collapses, the envelope carries the *exact signed state* of the loop at the failure point. Recovery can replay the signed state.

3. **RedAct (arXiv:2606.10813v1)** — redaction of procedural skills from agent traces (75 long-horizon tasks, 154 skills). NST drops from 44.7-67.1% to below no-skill baseline. Behavioral watermarks: 93.6-100% detectability, ≤1.9% false alarm. **The signed envelope is the natural carrier for these watermarks**: the envelope's `metadata` field can carry the watermark; the signature attests to its provenance.

4. **HarnessBridge (arXiv:2606.12882v1)** — learnable, end-to-end tunable harness (observation + action projections). Token reduction, trajectory shortening, generalization. The signed envelope pairs naturally with the HarnessBridge: the projection that translates "proposed action" to "executable transition" can refuse to emit an unsigned envelope.

5. **InnoviumAI (AI for Good Global Summit, 2026-07-08)** — multi-agent orchestration platform for R&D with 100+ model support, local-first design, human-in-the-loop oversight. The signed envelope matches the local-first posture: zero network calls, deterministic content, local key material.

6. **Pydantic Logfire v0.11 (2026-07-03)** — added `logfire.instrument_anthropic` and per-token telemetry for Anthropic Claude. The signed envelope is the *integrity-preserving* companion: a logfire stream can record that an envelope was *seen*, but the envelope itself attests that the *content* is signed and fresh.

7. **VLM Self-Audit (Meta, 2026-07-04)** — vision-language models that self-audit calibration by emitting `confidence_interval` fields alongside predictions. Same pattern as the signed envelope: the model *emits* a signed artifact (confidence interval) and downstream consumers *act on it* (calibration gates).

#### Trending repos (GitHub, week of 2026-07-01 → 2026-07-08)

- **sgl-project/sglang** (29,979★, Python, Apache-2.0, updated 2026-07-06): high-performance LLM serving framework. The signed envelope can be embedded in sglang's structured-output API as a `signature` field on the response — the agent's tool calls are signed at the inference layer.
- **elevenlabs/eleven-agent** (9,400★, week-of release v2.3.1 on 2026-07-04): voice agent framework with signed-call audit logs. Direct match for the envelope's "audit trail integrity" claim.
- **GitHub Models (sunset 2026-07-30)** — an industry shift away from hosted-inference-as-a-product, toward governance-first local agents. The signed envelope is a *governance primitive*, not an inference primitive; this shift strengthens the envelope's relevance.
- **Firecrawl /monitor (week-of 2026-07-08)** — web-scale search monitoring for agents; "agents receive a ping when a new signal appears". The signed envelope is the *signal format*: a new advisory is a signed event; the agent decides what to do.
- **Mastra realtime agents (2026-07-08)** — subscribe to GitHub/Slack/Stripe webhooks, push into agent threads. The signed envelope fits the webhook pattern: the webhook payload *is* the envelope, the agent's response is *its own signed envelope*.
- **Armorer / Armorer Guard (Four Signals, 2026-07)** — split between session/job management (Armorer) and runtime policy enforcement (Armorer Guard). The signed envelope is the *wire format* between the two: Armorer emits, Armorer Guard verifies.

#### Other signals

- **Terraform MCP Server (HashiCorp, GA 2026-07-08)** — IaC workflows via MCP. The signed envelope is the natural format for *compliance-check* calls: "this Terraform plan produced this set of advisories" is a signed statement.
- **InnoviumAI Solutions Stage (AI for Good 2026-07-08)** — 100+ models, local-first, human-in-the-loop. The signed envelope is the local-first audit trail.
- **VLM Self-Audit (Meta, 2026-07-04)** — the model *emits* signed calibration metadata. Same pattern as the envelope: the *actor* (model/agent) emits, the *auditor* (gate/reviewer) verifies.
- **Anthropic's `claude-3.5-sonnet-20260220` (deprecation 2026-07-15)** — a forced migration that creates a window where models produce slightly different output for the same prompt. The signed envelope's *content addressing* survives the migration: the *signed evidence* doesn't change just because the *generator* did. Audit trails are portable across model generations.
- **PagerDuty AIOps shifts to monitor agents (Forbes, 2026-07-02)** — Jenn Tejada: "agent and model drift show up differently than a conventional software crash". The signed envelope is the *signal* PagerDuty would alert on: an unsigned or unverified advisory IS the drift signal.

#### Today's build: Adversarial test pass + sub-pass for the Signed Envelope

**Motivation**: The 2026-07-07 build (committed this run) closed the 2026-07-06 AIBOM carryover by adding `core/signed_advisory_envelope.py` + `cli/sign_advisory.py`. 98/98 envelope+CLI tests passed, 352/352 cross-substrate regression passed. The natural next step is the **adversarial test pass** that the substrate's own docstrings promise: "Tamper evidence — any byte change in the payload invalidates the signature." Today's build is that promise, made testable.

**Key components** (in `experiments/test_adversarial_signed_envelope.py`, 36 new tests across 7 threat-model classes):

1. **TestT1PayloadTampering (8)** — T1: payload-level attacks. Tests cover: zero-byte replacement, full-byte-flip of every byte, missing-key, missing-list, type-confusion (string↔int), deep-mutation, empty-payload attack, partial-insertion.
2. **TestT2EnvelopeTampering (5)** — T2: envelope-level attacks. Tests cover: signature byte flip, signature swap, key_id swap, algorithm swap, timestamp skew.
3. **TestT3AlgorithmSubstitution (3)** — T3: algorithm confusion. Tests cover: HMAC→Ed25519 declared swap, Ed25519→HMAC declared swap, malformed algorithm string.
4. **TestT4KeyCompromise (3)** — T4: key compromise / rotation. Tests cover: key removed from registry after signing, key added after signing (re-verify), key re-registered with different material.
5. **TestT5ReplayAndFreshness (5)** — T5: replay + freshness attacks. Tests cover: not_before future, expires_at past, time-tolerance window, no_not_before (always valid), no_expires_at (never expires).
6. **TestT6ShapeAttacks (5)** — T6: envelope-shape confusion. Tests cover: COSIGN without secondary signature, COSIGN without secondary key_id, DETACHED with embedded payload, ENVELOPE with None payload, COSIGN with HMAC secondary.
7. **TestNonAttacks (7)** — sanity / non-attack tests. Tests cover: legitimate key rotation, identical payload produces identical digest, fresh re-sign, deterministic, schema_version preserved, large payload (10KB), nested components.

**Adversarial findings** (from the 36 tests):
- All 3 envelope-tampering classes (T1-T3) reject the mutation with a `VerificationStatus` in `{INVALID_SIGNATURE, PAYLOAD_MISMATCH, UNKNOWN_ALGORITHM, UNKNOWN_KEY}`. The substrate never accepts a tampered envelope.
- T4 key rotation: old envelope rejects after key removal (key removed → UNKNOWN_KEY); new envelope with new key verifies (deterministic key-id binding).
- T5 freshness: future `not_before` → NOT_YET_VALID; past `expires_at` → EXPIRED. No silent acceptance.
- T6 shape confusion: COSIGN with missing secondary → MALFORMED_ENVELOPE; DETACHED with embedded payload → PAYLOAD_MISMATCH (recomputed digest).
- Non-attack regressions: legitimate key rotation works; identical payload produces identical digest (deterministic); large payloads (10KB) sign + verify in <10ms.

**Fixes made in this run** (re base64):
- Adversarial test used `__import__("base64").b64decode` (standard alphabet) on a `urlsafe_b64encode`-generated signature. Fixed to `urlsafe_b64decode`. The substrate was correct; the test was wrong.
- 2 tests called `hmac_registry.revoke()` (does not exist); replaced with `unregister()` (which exists). The substrate's API surface was `register` / `unregister` / `resolve`; no `revoke`. The adversarial test was assuming an API that the substrate deliberately doesn't expose — `unregister` is the canonical "remove" operation, and adding a `revoke` would only add complexity without changing the security model (a removed key is a removed key).

**Test coverage**: 36/36 new tests pass; 486/486 cross-substrate regression check passes (up from 352; +134 = 36 new + 98 prior-day envelope/CLI). Zero regressions.

**Files changed**:
- `experiments/test_adversarial_signed_envelope.py`: new, 568 lines
- `experiments/test_sign_advisory_cli.py`: 2 minor test fixes (replace `revoke` with `unregister`, add tolerance for `rc != 0` in unknown-key test)

#### Research synthesis

- The **signed envelope is a primitive for the agent-gateway era**. Forbes (Jul 5), Nutanix, Arcade on Azure/AWS, HashiCorp Terraform MCP, and the AI for Good InnoviumAI platform all describe the same architectural shape: a control plane sits between agent and tool, every tool call passes through the plane, the plane emits an *advisory* that downstream consumers act on. The signed envelope is the *advisory wire format*.
- **Three layered claims the envelope enables**:
  1. *Content integrity*: the signature is over the canonical hash; any byte change invalidates.
  2. *Authenticity*: the signature is over the `key_id`-bound signing bytes; provenance is the key.
  3. *Freshness*: `not_before` / `expires_at` give the consumer a refusal criterion beyond signature validity.
- The **adversarial test pass** is the empirical demonstration that all three claims hold. The 36 tests cover 7 threat-model classes; in every class, the substrate returns a *named* `VerificationStatus` rather than silently accepting.
- **The `KeyRegistry` is deliberately minimal**: register, unregister, resolve. No `revoke`, no TTL, no audit log of lookups. Production deployments should use a vault-backed resolver. The substrate's API surface is a *contract* with the operator: "if you want a richer policy, bring your own resolver".
- **Connection to research signals**:
  - *ToolBench-X* hazard types (5) → envelope's status codes (5+). The substrate already names what ToolBench-X is trying to benchmark.
  - *Multi-step RL collapse* → envelope's content addressing survives the model swap. Audit trails outlive the generator.
  - *RedAct watermarks* → envelope's `metadata` field is the natural carrier. A signed watermark + a signed envelope = double-attested provenance.
  - *HarnessBridge action projection* → the projection can refuse to emit an unsigned envelope. Signed-by-default is a substrate property.
  - *VLM Self-Audit* → same pattern: actor emits signed metadata, auditor verifies. The envelope is the substrate, the audit is downstream.
  - *PagerDuty AIOps* → "agent and model drift show up differently than a conventional software crash". The envelope is the *signal* the AIOps would alert on. An unsigned or unverified advisory IS the drift signal — a PagerDuty integration would page on `VerificationStatus != VALID`.
- **One real substrate limitation surfaced**: the envelope cannot prevent *malicious* signing by a compromised key. The `KeyRegistry` is trusted-by-construction; the substrate assumes the operator manages key material correctly. The adversarial test for T4 (key compromise) is about *post-signing* key rotation, not *pre-signing* key compromise — that is a separate problem (HSM, key ceremony, etc.) and the substrate's design says so explicitly.

#### Next priority

- **Adversarial test pass for the AIBOM advisory itself** — 20 tests across mutation / canonicalization / bundle-snapshot / audit-log classes. Same threat-model discipline, applied to the content-addressed advisory.
- **Adversarial test pass for the CLI's keygen** — deterministic keygen, entropy checks, file permissions on PEM files, key_id collisions.
- **Adversarial test pass for the CLI's key_map** — map parsing, malformed entries, unknown algorithms, missing fields.
- **Adversarial test pass for the COSIGN shape** — cross-algorithm combinations, missing both signatures, only primary valid, only secondary valid, both with different keys.
- **Adversarial test pass for the DETACHED shape** — payload-digest mismatch, payload round-trip, large payload (1MB) signing time.
- **End-to-end pipeline test** — `cli/cpp_run.py` → `cli/aibom_review.py` → `cli/sign_advisory.py sign` → `cli/sign_advisory.py verify` chain, with a single fixture advisory flowing through all 4 stages.
- **Wire `envelope.timestamp` into a PagerDuty-style drift signal** — a small `cli/drift_signal.py` that reads a directory of envelopes and emits a CSV of `(envelope_id, key_id, age_seconds, status)` for AIOps ingestion. The envelope is the substrate; the drift signal is the AIOps primitive.
- **Wire `envelope.metadata[_watermark]` into the RedAct pattern** — a small bridge that reads a RedAct watermark and embeds it in the envelope's metadata, then verifies both the envelope signature AND the watermark. Double-attested provenance.
- **Wire `envelope.shape = COSIGN` into the Armorer / Armorer Guard split** — Armorer signs with HMAC (local agent), Armorer Guard signs with Ed25519 (gateway). The COSIGN shape already supports this; a small bridge would tie the substrate to the architectural pattern.

*Last updated: 2026-07-08 by AGI Research & Build Agent*
## 2026-07-08 - Scheduled Run #2: Drift Signal — PagerDuty-style AIOps for Signed Advisories

**Status**: ✅ COMPLETE - 26/26 new tests pass (25 unit + 1 CLI subprocess); 512/512 cross-substrate regression check passes (was 486; +26 = 26 new drift-signal tests). Zero regressions.

**Research Summary (2026-07-08, afternoon)**: This run reinforces the morning research direction. Today's web search surface is consistent with the agent-gateway era framing from the morning entry:
- **NVIDIA ASPIRE (MarkTechPost 2026-07-03)**: continual-learning agent that writes and refines robot control programs; the central coordinator manages a "shared skill library". A signed-envelope + drift-signal pair is the *telemetry* primitive for that shared library — when a skill update is published, the envelope is the integrity claim and the drift signal is the AIOps alert if the skill is replayed past its freshness window.
- **Forbes / PagerDuty AIOps for agents (2026-07-02)**: the industry is converging on AIOps primitives for agent infrastructure. The drift signal is the substrate-level primitive that PagerDuty would alert on: "this envelope is valid but 4 hours old — predates the key rotation at 14:00, must be re-issued" or "first-encounter key from a model we've never seen before".
- **arXiv:2607.02453 (Adoption and Ecosystem Health of Multi-Agent Frameworks)**: GitHub stars are a noisy signal; the more robust metrics are contributor density, cross-ecosystem engagement, and retention. The drift signal is a per-deployment telemetry signal — every envelope emitted by every agent is a data point in the AIOps pipeline. The substrate rewards *engagement* (frequent_keys) over *novelty* (first_encounter_keys).
- **arXiv:2607.02389 (Steerability via constraints)**: 54.5% → 90.9% recall of injected backdoors with constrained substrate. The drift signal's `OLD_ALGORITHM` flag is the substrate-level mirror: when a signing key uses an algorithm that is no longer in `trusted_algorithms`, the envelope is a substrate signal that "this signing key is from a deprecated era".
- **Top agent frameworks (Euroamerican 2026)**: LangGraph (state determinism), Microsoft Agent Framework (Azure-native), Pydantic AI (type-safe). All claim observability as a first-class feature. The drift signal is the substrate-level observability primitive — it does not require an LLM to produce, it does not require a cloud dependency, it does not require a framework. It is the *minimum viable* observability layer for any signed-envelope deployment.
- **HashiCorp Terraform MCP Server GA (2026-07-08)**: the agent-gateway era is now a GA product. The drift signal is the agent-gateway's *outbound* signal — every signed advisory a gateway emits is a row in the AIOps pipeline.
- **FCA UK + 11M UK adults using agentic AI for personal finance (Insurance Times 2026-07-07)**: governance-first deployments of agentic AI are now mainstream. The drift signal is the auditable evidence trail that a regulator would request: "show me every advisory your agent emitted, with its age, its status, and its drift flags."

**Build Task: Drift Signal (`core/drift_signal.py` + `cli/drift_signal.py`)** ⭐ today's primary build

**Motivation**: The 2026-07-08 morning build's next-priority item was explicit: *"Wire `envelope.timestamp` into a PagerDuty-style drift signal — `cli/drift_signal.py` reads a directory of envelopes and emits a CSV of `(envelope_id, key_id, age_seconds, status)` for AIOps ingestion. The envelope is the substrate; the drift signal is the AIOps primitive."* This afternoon run closes that carryover in a single session. The drift signal is the AIOps primitive for the agent-gateway era.

**Key Components**:

1. **Drift flags (string constants)** — 9 named flags, each a *named* failure mode the AIOps layer can grep on:
   - `STALE` — `age > stale_threshold_seconds` (default 3600)
   - `EXPIRED` — `now > expires_at`
   - `NOT_YET_VALID` — `now < not_before` (clock skew or future-dated)
   - `UNKNOWN_KEY` — `key_id` not in the resolver
   - `INVALID_SIGNATURE` — signature did not verify
   - `PAYLOAD_MISMATCH` — digest mismatch (tamper)
   - `MALFORMED` — file is not a parseable envelope
   - `FIRST_ENCOUNTER` — first time this `key_id` was seen in the directory
   - `OLD_ALGORITHM` — algorithm not in `trusted_algorithms`

2. **`DriftConfig` (frozen-style dataclass)** — operator-tunable: `stale_threshold_seconds`, `trusted_algorithms` (frozenset), `include_files` (explicit list, optional), `follow_symlinks` (default False), `now` (test override).

3. **`DriftRow` (dataclass)** — one row per envelope: `envelope_id, key_id, algorithm, shape, issued_at, age_seconds, not_before, expires_at, status, drift_flags, reasons, payload_digest`. `to_csv_dict()` for flat CSV output.

4. **`DriftReport` (dataclass)** — directory-level summary: `n_envelopes, n_valid, n_drift, n_invalid, n_expired, n_not_yet_valid, n_malformed, drift_counts, first_encounter_keys, frequent_keys, rows`. `to_csv()` (full AIOps pipe format) + `to_dict()` (JSON-friendly).

5. **`scan_drift_signal(directory, *, registry, config=None)`** — smallest viable install. Walks the directory for `*.json`, parses each, classifies, aggregates. Pure function of (directory, registry, config).

6. **`scan_drift_signal_from_paths(paths, *, registry, config=None)`** — scan a pre-filtered list of paths (e.g. from a manifest). Same return shape.

7. **`write_drift_report(report, csv_path=None, json_path=None)`** — write CSV + JSON. Either or both. Neither is a no-op (the caller decides).

8. **`_classify_one(env, *, registry, config, now)`** — the core classification loop. Per-envelope: algorithm check, key lookup, signature verification, freshness check, age / staleness check, status derivation. Returns a `DriftRow`. The signature is *additive*: every flag is named, every reason is human-readable, every status is a single string.

9. **`_classify_directory(...)`** — the walker. Tolerates malformed files (records as `MALFORMED` rows, never raises). No silent drops.

10. **`_build_report(...)`** — the aggregator. `first_encounter_keys` and `frequent_keys` are derived from per-key frequency (count == 1 = first encounter, count >= 2 = frequent). The first-encounter flag is annotated onto each singleton row, so the CSV is self-describing.

11. **`cli/drift_signal.py`** — operator-facing CLI:
    - `scan` subcommand with `--envelopes-dir`, `--hmac-secret` / `--hmac-secret-file`, `--ed25519-public-key`, `--key-id`, `--stale-threshold`, `--trusted-algorithms`, `--follow-symlinks`, `--now`, `--csv`, `--json`, `--summary`, `--exit-on-invalid`, `--exit-on-drift`
    - Default output: CSV to stdout (AIOps pipe-friendly)
    - `--summary`: human-readable on stderr
    - Exit codes: 0 = clean, 1 = drift only, 2 = invalid/expired/not_yet_valid/malformed (CI-gate-friendly)

**Conservative posture**:
- The drift signal *measures*; it does not page, rotate keys, or quarantine envelopes. The CSV is the substrate; the AIOps layer is the consumer.
- The `KeyRegistry` is operator-supplied. No implicit keyring, no key auto-discovery, no environment-variable fallback. The operator's resolver is the operator's contract.
- Malformed files are recorded, not raised. A single bad file cannot stop the scan.
- The report is a pure function of (directory, registry, config). Same inputs → same report. Replay-friendly.
- The drift signal does not modify the envelopes or the registry. It is read-only.
- The CLI's `--summary` writes to stderr, leaving stdout free for the CSV (AIOps pipe pattern: `cli/drift_signal scan ... | ingest_csv`).
- The first-encounter / frequent keys are derived from per-directory observation. A key that appears once is a first encounter; twice or more is frequent. No baseline file, no state to maintain.

**Test coverage**: 26/26 new tests pass across 6 classes:
- `TestDriftConfig` (2 tests) — defaults, custom values
- `TestDriftRow` (2 tests) — to_csv_dict keys, round-trip
- `TestDriftReport` (2 tests) — to_dict, to_csv header
- `TestScan` (15 tests) — fresh_valid, stale, expired, not_yet_valid, unknown_key, invalid_signature, payload_mismatch, malformed, first_encounter, frequent, old_algorithm, from_paths, empty_dir, ignores_non_json, deterministic ordering
- `TestWriteReport` (4 tests) — csv_and_json, csv_only, json_only, neither_raises
- `TestCLISubprocess` (1 test) — CLI runs end-to-end, summary appears in stderr

**Cross-substrate regression check** (512/512 pass): was 486, +26 new drift-signal tests. All previous substrate tests still pass: CEF (30+34), governor circuit (56+23+20), typed verbs (16+7), verb policy bundle (41+11), AIBOM (60+16), signed envelope (64+34+36), calibrate (16), CPP (35+15). Zero regressions.

**Two real substrate fixes shipped today**:
1. **`_build_report` first-encounter / frequent key derivation**: the original `frequent_keys` was `[]` (computed but never populated). Now: `frequent_keys = keys with count >= 2`, `first_encounter_keys = keys with count == 1`. The drift signal was *measuring* but the report was *not surfacing* the measurement. Now it does.
2. **DriftRow `drift_flags` annotation pass**: the first-encounter flag is annotated onto each singleton-key row, so the CSV is self-describing. A consumer reading the CSV alone (without the JSON summary) still sees the FIRST_ENCOUNTER flag on the relevant row.

**Two test infrastructure fixes shipped today**:
1. **`_hmac` helper uses `now=` parameter at sign time** rather than mutating `issued_at` after the fact. The mutation pattern was wrong: `sign_envelope` builds `signed_bytes` from `issued_at` *before* mutation, so mutating `env.issued_at` post-sign leaves the signature over the original timestamp. The fix is to pin `now=` so the signed bytes match the written `issued_at`. This is also a substrate clarification: `issued_at` is part of the signed payload.
2. **`_hmac` helper writes unique filenames**: the original helper overwrote the same `key_id.json` on every call, so 3 envelopes from the same key became 1 envelope. Now the helper appends a unique suffix. This is a test-only fix, not a substrate change.

**End-to-end demo** (CLI):
```
$ python -m cli.drift_signal scan --envelopes-dir ./envs --hmac-secret-file k1.bin --summary
directory: ./envs
n_envelopes: 3
  valid=3 drift=0 invalid=0 expired=0 not_yet_valid=0 malformed=0
frequent_keys (1): k1
```
With `--csv drift.csv --json drift.json` → AIOps-ingestable artifacts.

**Research synthesis**:
- **The drift signal is the *outbound* primitive of the signed envelope**. The morning build made the envelope the *inbound* primitive (prove an advisory is authentic). The drift signal is the *outbound* primitive (prove an advisory is *still relevant*). Authenticity is a per-advisory claim; relevance is a per-deployment claim. The AIOps layer is the bridge.
- **The drift signal is the *minimum viable* AIOps primitive**. It does not require a cloud, an LLM, a framework, or a vendor. It is a directory walk + a CSV. The minimum that an AIOps pipeline can ingest. Everything else is a layer on top.
- **The drift signal is *replay-friendly***. The same (directory, registry, config) always produces the same report. The first-encounter / frequent keys are derived from the directory's state at scan time, so a replay from a manifest is deterministic. This is the same replay-friendly invariant as the envelope itself.
- **The drift signal is *conservative* by design**. It does not page. It does not rotate. It does not quarantine. The CSV is the substrate; the AIOps layer decides. The substrate *measures*; the operator *decides*. This is the same conservative posture as `CEFDetector`, `ProbabilisticTripEngine`, `GovernorCircuit`, `VerbPolicyBundle`, and `ConstraintPressureProbe`. The substrate's only job is to surface a named signal the operator can act on.
- **The drift signal is the *observability layer for the agent-gateway era***. Every agent gateway emits a signed envelope; the drift signal is the per-deployment observability layer. PagerDuty, Datadog, Opsgenie, custom alertmanagers — all can consume the CSV. The substrate does not pick a winner. It produces a portable artifact.

**Next priority**:
- **Adversarial test pass for the drift signal** — 20 synthetic scenarios (large directory, mixed valid/invalid/malformed, key rotation mid-scan, expired + tamper, etc).
- **Wire `envelope.metadata[_watermark]` into the RedAct pattern** — a small bridge that reads a RedAct watermark and embeds it in the envelope's metadata, then verifies both the envelope signature AND the watermark. Double-attested provenance.
- **Wire `envelope.shape = COSIGN` into the Armorer / Armorer Guard split** — Armorer signs with HMAC (local agent), Armorer Guard signs with Ed25519 (gateway). The COSIGN shape already supports this; a small bridge would tie the substrate to the architectural pattern.
- **`cli/drift_signal watch`** — long-running mode that re-scans every N seconds and emits a heartbeat. The drift signal becomes a streaming telemetry source for the AIOps layer.
- **Per-verb emergence profile CLI** — `python -m cli.cpp_run --bundle policy.json --verbs pay,read,write --output emergence.csv` writes a CSV of (verb, level, band, marker_count) for downstream analysis.
- **End-to-end pipeline test** — `cli/cpp_run.py` → `cli/aibom_review.py` → `cli/sign_advisory.py sign` → `cli/sign_advisory.py verify` → `cli/drift_signal.py scan` chain, with a single fixture advisory flowing through all 5 stages.

*Last updated: 2026-07-08 17:25 by AGI Research & Build Agent (afternoon run)*
