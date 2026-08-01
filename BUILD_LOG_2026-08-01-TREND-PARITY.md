# Build Log — 2026-08-01: Trend Evidence-Status Parity

## Research synthesis

The current two-week research signal favors explicit state, evidence-grounded skill evolution, test-time heterogeneity, and reviewable self-improvement rather than unconstrained autonomous mutation:

- **From Memory to Skills: Evidence-Grounded Co-Evolution** (arXiv:2607.16621) turns memory traces into callable skills only when supported by evidence, with boundaries, verification rules, and reliability estimates.
- **Can AI agents conduct open-ended AI research?** (arXiv:2607.07916) finds meaningful engineering capability but persistent weakness in nuanced and creative research stages, supporting explicit verification boundaries.
- **Cognitive Convergence** (arXiv:2607.26179) is a conceptual account of similarities between LLM and human cognition; it is relevant framing, not evidence of AGI.
- **Skill Self-Play** (arXiv:2607.22529) combines proposer/solver/controller loops with verifiable skill execution, reinforcing that capability growth needs grounded evaluation.
- **PoTRE** (arXiv:2607.20268) uses heterogeneous reasoning roles plus task-adaptive aggregation, a useful architecture pattern for independent checks.
- **Frontis-MA1 / OpenMLE** (arXiv:2607.28568) studies execution-grounded recursive improvement in ML engineering; its operator separation and benchmark feedback are directly relevant to this repository's review-only posture.
- Open-source activity signals included `antoinezambelli/forge` (tool-calling reliability and workflow constraints), `Nanako0129/pilotfish` (multi-model orchestration with independent verification), and `openai/openai-agents-python` v0.18.3 (session, sandbox, concurrency, and tracing reliability). These are activity signals, not a controlled popularity ranking.

## Build

Closed the previous run's next priority: trend inputs whose schema-invalid evidence is stored under `points[].line_provenance` now receive the same machine-readable evidence counts and Markdown presentation as ordinary fleet inputs.

- Added a shared evidence-line projection that reads fleet `lines` first and falls back to trend point `line_provenance`.
- Trend-derived Markdown findings retain `snapshot_id` alongside source ID and physical line number.
- JSON and Markdown use the same projected status counts; no independent recounting remains.
- Added a CLI regression covering trend JSON and Markdown parity.

The change is reporting-only. Raw trend/fleet envelopes are preserved, invalid evidence remains visible, and `automatic_action_taken=False`; no policy, signed decision, action application, evidence repair, or self-modification is performed.

## Validation

- CAGE-1 review/advisory/fleet/trend/report regression: **81 passed**.
- `python -m py_compile core/cage1_advisory.py experiments/test_cage1_review_decision.py` passed.
- `git diff --check` passed.
- Manual trend Markdown output confirmed `total=1`, `schema-invalid=1`, source `trend-member.jsonl`, physical line `17`, and snapshot `t1`.

## Next priority

Add a trend JSON/Markdown regression for mixed valid plus schema-invalid `line_provenance` across multiple snapshots, preserving snapshot/source order and keeping policy, action application, evidence repair, and self-modification review-gated.
