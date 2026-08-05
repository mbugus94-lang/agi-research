# 2026-08-05 — Scheduled Run: CLI Same-Decision Ambiguity Boundary

## Status

COMPLETE — added one operator-facing regression; complete CAGE-1 regression remains **192/192**. No production behavior or policy changed.

## Research synthesis

Recent work emphasizes explicit memory operations, trajectory-level validation, evidence depth, and visible execution protocols. Current GitHub activity signals included Hermes Agent, Agent-Reach, and nanobot; the recurring open-source direction is persistent memory plus broad tools in inspectable local harnesses.

## Build

Added `test_review_cli_keeps_same_decisions_ambiguous_and_review_only` to `experiments/test_cage1_review_decision.py`. It invokes `cli.cage1_review` with two independently signed `defer` envelopes for one advisory and verifies `status="ambiguous"`, `valid=false`, preserved operator order, no selected decision, and no automatic action.

## Validation

- Focused review/consumer regression: **36 passed**.
- Complete CAGE-1 regression: **192 passed**.
- `python -m compileall -q core cli experiments/test_cage1_review_decision.py` passed.
- `git diff --check` passed.

## Safety and next priority

The CLI remains review-only. Duplicate or conflicting valid decisions are evidence requiring operator review, never permission for automatic selection. Next priority: JSONL audit-output parity coverage for the review CLI, then reassess before changing production behavior.

## Sources

- https://arxiv.org/abs/2607.20064v2
- https://arxiv.org/abs/2607.28802v1
- https://arxiv.org/abs/2607.29405v1
- https://arxiv.org/abs/2607.17947v1
- https://arxiv.org/abs/2607.28287v1
- https://github.com/NousResearch/hermes-agent
- https://github.com/Panniantong/Agent-Reach
- https://github.com/HKUDS/nanobot
