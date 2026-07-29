# Build Log - 2026-07-29 - Schema-Invalid Advisory Projection

## Status

Complete. The review-only CAGE-1 advisory layer now projects individual `invalid_schema` audit lines into explicit operator findings, retaining source and physical-line provenance. Focused regression passes 131/131.

## Research synthesis

Recent work on operational hallucination, long-context skill failure, autonomy governance, synchronized context, and explicit error memory supports a strict boundary: preserve malformed evidence, make derived findings traceable, and keep advisory output separate from execution authority.

## Implementation

- Added `_schema_invalid_findings(...)` to `core/cage1_advisory.py`.
- Direct fleet evidence scans `lines`; trend evidence scans each point's `line_provenance`.
- Findings include source ID, physical line, and parser reason.
- Schema-invalid evidence is `critical` / `escalate` and requires operator review.
- Raw envelopes remain unchanged; `automatic_action_taken` remains false.
- Added two adversarial tests in `experiments/test_cage1_advisory.py`.

## Safety boundary

Verification and projection only. No policy, decision, action, evidence repair, or self-modification is performed.

## Validation

- Focused CAGE-1 advisory/fleet/trend/decision regression: 131 passed.
- `python -m py_compile core/cage1_advisory.py` passed.
- `git diff --check` passes.

## Next priority

Add a review-only CLI fixture/report mode that exposes schema-invalid findings in JSON and Markdown without changing signed-decision verification.
