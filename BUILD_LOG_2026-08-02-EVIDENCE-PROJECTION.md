# Build Log: Reusable Evidence-Projection Contract

**Date:** 2026-08-02
**Status:** Complete

## Scope

Create one reusable, read-only projection contract for CAGE-1 fleet and trend evidence so machine-readable counts and Markdown rendering cannot drift.

## Changes

- Added `project_evidence_lines(source)` in `core/cage1_advisory.py`.
- Added `project_evidence_status(source)` in `core/cage1_advisory.py`.
- Routed advisory JSON and Markdown evidence through the shared projection.
- Added two regression tests covering direct fleet/trend shapes and the normalized fleet-plus-trend envelope.

## Safety boundary

The change only projects and counts preserved evidence. It does not repair malformed records, change policy, verify or apply operator decisions, execute actions, or self-modify.

## Validation

- `python -m pytest -q experiments/test_cage1_review_decision.py experiments/test_cage1_advisory.py` — 24 passed.
- `python -m py_compile core/cage1_advisory.py experiments/test_cage1_review_decision.py` — passed.
- `git diff --check` — passed.

## Next priority

Add deterministic multi-snapshot trend parity coverage including valid, schema-invalid, and other-status records, then keep the projection review-only.
