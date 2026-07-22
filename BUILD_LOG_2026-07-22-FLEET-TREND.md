# Build Log — 2026-07-22 — CAGE-1 Fleet Trend Envelope

## Scope

This run completed the next priority from the adversarial fleet/report validation build: expose the existing read-only fleet evidence alongside the compact CAGE-1 trend and comparison output.

## Research synthesis

Recent research converges on verifiable, bounded state rather than opaque end-state scores:

- DeepSearch-World (arXiv:2607.07820) uses deterministic tools, progress verification, grounded reflection, and failure recovery for self-improving search agents.
- DeepStress (arXiv:2607.13920) evaluates agents under controlled unreliable evidence; malformed and low-quality evidence should remain visible rather than silently becoming a score.
- A hierarchical memory architecture (arXiv:2607.07666) bounds long-horizon state and preserves specialist oversight.
- Reward-Free Evolving Agents (arXiv:2607.14408) supports pairwise review and rejects blind auto-application of self-improvements.
- Speculate with Memory (arXiv:2607.12236) separates predictive memory from the actor trajectory, reinforcing observational evaluation.
- RxBrain (arXiv:2607.14187) couples plans to grounded world-state predictions, supporting inspectable intermediate evidence.

Open-source signals included Forge (self-hosted tool-calling with guardrails), pmb (local-first persistent memory), and OpenAI Agents Python v0.18.3 (multi-agent and session-memory fixes). These are activity/architecture signals, not a controlled popularity ranking.

## Build

Implemented one incremental task (D):

- Added `CAGE1FleetTrend`, a serializable envelope containing both `CAGE1Trend` and the provenance-preserving `CAGE1Fleet`.
- Added `trend_fleet_snapshots(...)`, which reuses the compact trend and the existing fleet aggregator without mutating snapshots or applying policy.
- Updated `--compare-snapshot` in `cli/cage1_report.py` to emit the fleet envelope in JSON and Markdown, preserving ordered sessions, digest lineage, anomalies, invalid fields, and explicit unmeasured evidence.
- Exported the new public type and function from `core`.
- Added regression coverage for fleet provenance, anomaly immutability, and CLI comparison output.

Safety boundary: this is read-only reporting. No policy, memory repair, automatic remediation, or self-modification was added.

## Validation

- Focused CAGE-1/memory/retrieval/advisory regression: **230 passed**.
- `python -m py_compile ...`: passed.
- `git diff --check`: passed.

## Next priority

Add a review-only advisory projection for fleet/trend anomalies only if it preserves the raw fleet envelope and requires an explicit operator decision. Do not auto-apply policy or self-modification changes.
