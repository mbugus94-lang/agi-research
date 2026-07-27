# Build Log - 2026-07-27 - Preserve Malformed Fleet Decision Audit Lines

## Status

Complete. The verification-only CAGE-1 fleet audit loader now preserves malformed JSONL records instead of aborting the entire member file. Focused CAGE-1 fleet/report regression passes 127/127.

## Research synthesis

Recent work on operational hallucination and safety drift, layered oversight, heterogeneous verification, tamper-evident event timelines, and inspectable agent state all points to the same implementation rule: evidence must stay lossless, attributable, and separate from action. Open-source signals checked were pilotfish, fable-harness, and Meterless/Meterless.

## Implementation

- `core/cage1_decision_fleet.py` now parses each nonblank JSONL line independently.
- Invalid JSON becomes a `malformed_json` `FleetAuditLine`; valid JSON arrays/values that are not objects become `malformed_record` lines.
- Each malformed line retains source ID, source path, physical line number, and a reason.
- Valid records retain their embedded logical `line_number`; malformed records use the physical line number.
- `FleetAuditLine.to_dict()` includes `reason`.
- Added two adversarial tests to `experiments/test_cage1_decision_fleet.py` covering loader and CLI behavior.

## Safety boundary

No policy, decision, action, evidence repair, or self-modification is performed. Invalid records remain visible and force a degraded fleet status.

## Validation

- Focused suite: 127 passed.
- `python -m py_compile core/cage1_decision_fleet.py cli/cage1_fleet_audit.py` passed.
- `git diff --check` passed.

## Next priority

Validate audit-line status and line-number fields explicitly while preserving lossless malformed-record handling. Policy and self-modification remain review-gated.
