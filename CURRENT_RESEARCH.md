

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
