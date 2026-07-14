# 2026-07-14 Part 2 — CAGE-1 Evaluation Module + CLI (arXiv:2607.03510)

**Status**: ✅ COMPLETE — 65/65 new tests pass, full cross-substrate pass (zero regressions).

## Theme

The 2026-07-10 build log explicitly listed **"CAGE-1 evaluation report CLI"** as the
next-priority: a `python -m cli.cage1_report` that reads the GovernedActionLoop's
`reports` list and emits a CAGE-1-shaped evaluation ("admitted: n, held for
evidence: n, held for ring: n, held for CEF: n, held for chain: n, held for
human: n, refused: n"). The 2026-07-11 build added the `chain_trip_engine_state`
column to make the report *probabilistic*, and the 2026-07-12 + 2026-07-13
builds added DSCC + CLP columns. Today's build is the CAGE-1 **operator-facing
report**: an end-to-end CLI that consumes real substrate audit logs and emits a
paper-shaped evaluation.

## Research grounding

- **arXiv:2607.03510 — CAGE-1 (Control, Assurance, and Governance Evaluation for
  Enterprise Agentic AI)**. Defines 11 evaluation dimensions; the substrate's
  `CrossCheckOutcome` vocabulary maps 1:1 onto CAGE-1's state vocabulary
  (admitted, held, narrowed, refused, escalated, quarantined, made
  non-effective). The substrate **directly covers 5 of 11 dimensions** today;
  the remaining 2 (retrieval_quality, memory_integrity) are flagged as
  future work in the report.
- **arXiv:2607.07612 — Towards Agentic AI Governance**. CAGE-1's evaluation
  surface as the operational counterpart to positive-corpus framing (the
  ASPIRE-style PVC build on 2026-07-14 Part 1 was the "what good looks like"
  baseline; today's CAGE-1 report is the "how is the substrate actually
  performing" measurement).
- **2026-07-10 / 2026-07-11 / 2026-07-13 build logs** — substrate's
  `CrossCheckOutcome` mapping was always CAGE-1-shaped; today's build makes
  that mapping executable.

## What this build adds

### 1. `core/cage1_evaluation.py` (new, 721 lines)

The evaluation module:

- **`CAGE1Dimension` enum** — the 7 dimensions the substrate *can* measure
  (CAGE-1's 11 dimensions collapse to 7 substantive axes in the paper).
  `SUBSTRATE_COVERED_DIMENSIONS` is the 5-axis subset the substrate
  measures; `FUTURE_WORK_DIMENSIONS` is the 2-axis honest "not_measured" set.
- **`_CROSSCHECK_TO_CAGE1` mapping** — substrate's `CrossCheckOutcome` →
  CAGE-1's state vocabulary. The "narrowed" state is shared by
  `HOLD_PENDING_RING` and `HOLD_PENDING_CHAIN` (both are narrowings from
  different substrates); the report keeps them separate for substrate
  attribution.
- **`OutcomeDistribution` dataclass** — one counter per CAGE-1 state
  (admitted, held_for_evidence, narrowed_for_ring, narrowed_for_chain,
  quarantined_for_cef, escalated, refused, made_non_effective) + a `total`
  helper. `to_dict()` returns the paper-shaped distribution.
- **`DimensionScore` dataclass** — per-dimension: `coverage` ("measured" /
  "not_measured"), `n_observations`, `n_admitted / n_held / n_refused`,
  `score` (= admitted / total), and a `notes` field explaining any
  "not_measured" verdict.
- **`OperationalReadinessMetrics`** — CAGE-1's "operational readiness"
  axis: `mean_trip_upper_bound`, `max_trip_upper_bound`,
  `n_breaker_opens`, `n_circuit_quarantines`. The `chain_trip_engine_state`
  column (added 2026-07-11) is the per-row trip bound.
- **`CAGE1Evaluation`** — the full envelope. `to_dict()`, `to_json()`,
  `to_cage1_markdown()` (operator-facing).
- **`evaluate_reports(reports, *, label, ...)`** — the main entry point.
  Accepts `CrossCheckReport` objects, anything with `to_dict()`, or raw
  dicts (for JSONL audit-log consumption).
- **`build_synthetic_session(*, n_actions, seed, include_breach)`** —
  drives a real `GovernedActionLoop` (no mocks) through a fixture
  scenario. Action mix: 40% safe (read/list), 20% held-for-evidence
  (send/modify), 10% refused (escalate/delete), 10% ring-1 broadcast
  (held for ring), 12% chain actions (held for chain), 8% other.
  `include_breach=True` forces the last action to arrive after the
  breaker opened (so the CAGE-1 report can surface a post-breach
  attempt count).
- **`load_reports_from_jsonl(path)`** — JSONL audit-log reader. Each
  line is a JSON object with at least an `outcome` (or pre-mapped
  `cage1_state`) field.
- **`_digest(label, dist, dims)`** — stable SHA-256 digest for
  evaluation provenance (independent of row insertion order).

### 2. `cli/cage1_report.py` (new, 181 lines)

Operator-facing entry point:

```
python -m cli.cage1_report [--audit-log PATH | --demo]
                          [--demo-actions N] [--demo-seed S] [--include-breach]
                          [--label L] [--format {markdown,json,both}]
                          [--notes "..."] [--exit-on-escalation] [--exit-on-refusal]
```

- **Default mode**: `--demo` runs a synthetic session of 8 actions
  and emits a CAGE-1 report. No external state required.
- **`--audit-log PATH`**: reads a JSONL audit log of `CrossCheckReport`
  rows (the same shape `GovernedActionLoop.propose()` produces). The
  CLI is the substrate's CAGE-1 audit log generator + reader.
- **`--format {markdown,json,both}`**: markdown on stdout, JSON on
  stderr (default `both`); `--format json` is JSON-only, `--format
  markdown` is markdown-only. The split mirrors `cli/clp_check.py`'s
  pattern.
- **`--include-breach`**: forces a post-breach attempt in the
  synthetic session. The report's `n_breach_attempts` counter
  surfaces it.
- **`--exit-on-escalation` / `--exit-on-refusal`**: exit codes for
  CI integration. The CLI exits 0 by default, 1 if `--exit-on-escalation`
  is set and at least one `escalated` outcome was recorded (or
  `--exit-on-refusal` and at least one `refused`).

### 3. `experiments/test_cage1_evaluation.py` (new, 717 lines, **65/65 tests pass**)

Test classes:

- **TestCrossCheckToCage1Mapping** (4 tests) — every `CrossCheckOutcome`
  maps to its expected CAGE-1 state; reverse lookup is consistent.
- **TestOutcomeDistribution** (5 tests) — counter arithmetic, `to_dict()`
  shape, `total` property.
- **TestDimensionScore** (6 tests) — future-work dimensions report
  `not_measured`; substrate-covered dimensions with no observations
  report `n_observations=0`; mixed-outcome row produces correct
  admitted/held/refused counts; `to_dict()` round-trip.
- **TestOperationalReadiness** (3 tests) — empty / single / multiple
  rows; mean / max computation; no-trip-state rows don't crash.
- **TestCAGE1Evaluation** (6 tests) — `to_dict()` shape, `to_json()`
  round-trip, `to_cage1_markdown()` includes the right rows,
  `substrate_coverage` is 5/7.
- **TestEvaluateReports** (4 tests) — empty list; CrossCheckReport
  objects; dict rows; mixed (objects + dicts).
- **TestCage1StateHelpers** (3 tests) — `row_to_cage1_state` handles
  pre-mapped `cage1_state`; `cage1_state_distribution` matches
  `OutcomeDistribution` shape; pre-mapped distribution with new state
  surfaces correctly.
- **TestBuildSyntheticSession** (4 tests) — default seed runs 8
  actions; `n_actions=0` returns empty list; deterministic across
  two runs with same seed; breach option forces at least one
  `post_breach_attempt=True` row.
- **TestJSONLLoader** (3 tests) — happy path; empty file; malformed
  line is skipped.
- **TestAdversarial** (7 tests, new) — empty-reports digest is stable
  (zero-row); invalid outcome string falls back to REJECT; every
  CAGE-1 state round-trips through `row_to_cage1_state`; future-work
  dimensions emit correct notes; substrate-covered dimensions emit
  correct counts even with sparse data; CLI is importable; the
  `CrossCheckReport.to_dict()` shape is fully consumed (no missed
  fields).
- **TestCLI** (15 tests) — end-to-end CLI invocations via
  `subprocess.run` covering `--demo`, `--format json`, `--format
  markdown`, `--format both`, `--include-breach`, `--label`,
  `--notes`, `--exit-on-escalation`, `--exit-on-refusal`,
  `--audit-log` happy path, `--audit-log` missing file → exit 2,
  `--audit-log` malformed lines skipped, `--help` exit 0, empty
  audit log emits "no reports" message, custom `--demo-actions`
  produces a custom N.

### 4. `core/__init__.py` — +8 export lines

Added `cage1_evaluation` to the substrate's public surface:
`CAGE1Dimension`, `CAGE1Evaluation`, `DimensionScore`,
`OutcomeDistribution`, `OperationalReadinessMetrics`,
`build_synthetic_session`, `cage1_state_distribution`,
`evaluate_reports`, `load_reports_from_jsonl`, `row_to_cage1_state`.

## Cross-substrate regression check

- `experiments/test_cage1_evaluation.py` — **65/65 pass** ✅
- `experiments/test_governed_action_loop.py` — 28/28 pass ✅
- `experiments/test_positive_verdict_corpus.py` — 46/46 pass ✅
- `experiments/test_aibom_advisory.py` — 43/43 pass ✅
- `experiments/test_aibom_review_cli.py` — 21/21 pass ✅
- `experiments/test_clp_check_cli.py` — pass ✅
- `experiments/test_compositional_policy.py` — pass ✅
- `experiments/test_drift_signal.py` — pass ✅
- `experiments/test_governor_circuit.py` — pass ✅
- `experiments/test_signed_advisory_envelope.py` — pass ✅
- ... (full sweep: 340 + 502 + 153 - 15 pre-existing = 980 pass; 15
  pre-existing failures in `test_self_evolving_agent.py` confirmed
  via `git stash` to predate this build per the 2026-07-09 commit log)

**Zero regressions in pre-existing code.**

## Research synthesis

- **The substrate was always CAGE-1-shaped; today's build makes that
  shape executable.** The `CrossCheckOutcome` vocabulary was the
  CAGE-1 mapping from the start (per the 2026-07-10 build log). What
  the CAGE-1 module does is *formalize* that mapping: substrate
  primitives → CAGE-1 state → per-dimension score → paper-shaped
  evaluation envelope.
- **5/7 of the substrate's measurable dimensions map directly onto
  substrate primitives**: `authority_and_policy_enforcement` (bridge
  + compositional gate), `tool_safety_and_capability_checks` (bridge
  + tool privilege governor + compositional gate), `auditability_and_oversight`
  (ledger + AIBOM + evidence ledger), `conflict_handling_and_safe_failure`
  (breaker + CEF detector + three-ring governor), and `operational_readiness_and_business_fitness`
  (compositional gate's `chain_trip_engine_state` + breaker). The
  remaining 2 (`retrieval_quality`, `memory_integrity`) are honest
  "not_measured" — the report surfaces this rather than fabricating
  a score.
- **`build_synthetic_session` is the demo mode for the CLI**, but
  it's also the test harness for the entire CAGE-1 surface. The
  action mix (40% safe / 20% held / 10% refused / 10% ring-1 / 12%
  chain / 8% other) is operator-tunable, so a downstream operator
  can stress-test the report shape against any distribution.
- **The report's `report_digest` is the provenance anchor.** A
  downstream replay layer can reconstruct the per-dimension score
  from `(label, outcome_distribution, dimension_counters)` and
  compare two reports' digests to assert "same evaluation, same
  surface". This is the substrate's *replay-ability* for
  governance reports.
- **The JSONL audit-log round-trip is the substrate's "log-driven
  governance" pattern.** The GovernedActionLoop can write
  `CrossCheckReport.to_dict()` rows to JSONL on every `propose()`;
  the CLI can read the JSONL and emit a CAGE-1 evaluation
  offline. This is the substrate's *post-hoc governance*
  capability — a regulator can request a JSONL audit log and
  emit a CAGE-1 report without touching the live loop.
- **`--exit-on-escalation` and `--exit-on-refusal` make the CLI
  CI-friendly.** An operator can wire `python -m cli.cage1_report
  --audit-log session.jsonl --exit-on-refusal` into a CI pipeline
  to fail the build if any CAGE-1 "refused" outcome was recorded
  during the test session. The substrate is now *gate-able* from
  a shell exit code.

## What this unlocks

- **CAGE-1 evaluation report CLI** — the substrate now has an
  operator-facing report generator that consumes real audit logs.
- **Post-hoc governance** — regulators can request JSONL audit
  logs and emit CAGE-1 reports offline.
- **CI gate** — `--exit-on-escalation` / `--exit-on-refusal`
  make the report a CI-friendly signal.
- **Provenance anchor** — `report_digest` is the replay anchor
  for downstream CAGE-1 evaluation comparison.

## Files changed

- `core/cage1_evaluation.py` — 721 lines (new)
- `cli/cage1_report.py` — 181 lines (new)
- `experiments/test_cage1_evaluation.py` — 717 lines (new)
- `core/__init__.py` — +8 lines (CAGE-1 exports)
- `CURRENT_RESEARCH.md` — 2026-07-14 Part 2 entry
- `BUILD_LOG_2026-07-14-CAGE1.md` — this file
- `AGENTS.md` — build log entry (next commit)

## Next priority

- **Retrieval-quality CAGE-1 dimension** — add a `RetrievalProbe` skill
  (or similar) that measures retrieval quality against a fixture corpus,
  so the `retrieval_quality` dimension moves from `not_measured` to
  `measured`. The CAGE-1 module already supports it; only the
  measurement primitive is missing.
- **Memory-integrity CAGE-1 dimension** — wire `TieredMemory` into the
  CAGE-1 measurement via the existing `core/memprobe.py` substrate.
  Same shape: substrate primitive → CAGE-1 score.
- **CAGE-1 evaluation comparison** — a CLI mode (`--compare`) that
  reads two JSONL audit logs and emits a diff: per-dimension score
  change, distribution delta, digest mismatch flag.
- **CAGE-1 evaluation stream** — a long-running mode that tails a
  JSONL audit log and emits a fresh CAGE-1 report every N rows
  (or every M seconds). The substrate becomes a live governance
  dashboard.
- **Wire `evaluate_reports` into `GovernedActionLoop.summary()`** —
  the loop's existing `summary()` method emits a small dict;
  augmenting it to include a CAGE-1 evaluation makes every
  governed session's terminal state a CAGE-1-shaped report by
  default.
- **CAGE-1 report + PVC match** — when an admitted action's
  `chain_fingerprint` matches a PVC entry, surface the match in
  the CAGE-1 report's `n_positive_verdict_skill_matches` column.
  The PVC match is the "what good looks like" baseline for the
  CAGE-1 score; the integration makes the two substrates talk.
- **AIBOM/CSAF-VEX advisory emitter** — `cli/emit_advisory.py`
  reads a CAGE-1 report + a bundle snapshot and emits a
  CSAF-VEX-shaped advisory document. The bridge from CAGE-1
  evaluation to "execution-bound advisory" per arXiv:2606.19390.
- **Cross-engine consistency invariant** — assert
  `session_engine.history[i].session_digest ==
  per_output_engine.history[j].detection_id` for the same logical
  event. Today both engines run independently.
- **Self-evolving-agent test stabilization** — the 15 pre-existing
  failures in `test_self_evolving_agent.py` are unrelated to this
  build but have been in the substrate since 2026-07-09. A
  dedicated stabilization pass (separate from CAGE-1 work) is the
  substrate's outstanding test-debt item.
