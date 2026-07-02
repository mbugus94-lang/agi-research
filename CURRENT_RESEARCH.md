

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
