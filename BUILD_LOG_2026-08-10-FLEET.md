# 2026-08-10 — Ordered Per-Verb CAGE-1 Fleet Aggregation

## Research

Recent arXiv work emphasized a control/governance plane distinct from runtime execution (AOS), bounded decomposition plus verification across backends (OneDayAgent), cost-aware milestone orchestration (EASy), scaffold-independent planning (DCAS), reflective experience memory without weight updates (REAPER), and held-out rollback-aware harness evolution (HarnessCompass).

GitHub activity signals included Prime Agent, NVIDIA NeMo labs-OO-Agents, Meterless, and Openwork. These are ecosystem signals rather than a controlled popularity ranking.

## Build

Added a read-only fleet layer over serialized per-verb CAGE-1 comparison snapshots:

- `core/cage1_verb_fleet.py`
- `cli/cage1_verb_fleet.py`
- `experiments/test_cage1_verb_fleet.py`
- exports in `core/__init__.py`

The layer retains ordered snapshot IDs, digest lineage, unioned verb identities, added/removed coverage, status counts, observation deltas, and latest worst state. Added and removed verbs are explicitly treated as coverage changes. JSON and Markdown are available through the CLI. No policy, evidence, decision, action, or self-modification state is changed.

## Validation

- Fleet tests: 5 passed.
- Adjacent comparison tests: 5 passed.
- Compilation and `git diff --check`: passed.

## Next priority

Keep the fleet output review-only. Add JSON/Markdown parity coverage only if a real mismatch remains; otherwise consider a provenance-preserving join with decision/advisory evidence.
