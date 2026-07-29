# Build Log - 2026-07-29 - Review-Only Schema-Invalid CLI Fixture

## Status

Complete. Added a deterministic `cli.cage1_review --fixture schema-invalid` mode with JSON and Markdown output. Focused review/advisory regression passes 14/14; the broader CAGE-1 fleet/trend/advisory/decision/report regression passes 158/158.

## Research synthesis

Current agent research favors typed harnesses, explicit state, externally grounded evaluation, and rollback/review boundaries. This build applies those principles to the audit-report surface: schema-invalid evidence is reproducibly visible, provenance is retained, and the advisory remains non-authoritative.

## Implementation

- Added a `schema-invalid` fixture to `cli/cage1_review.py`.
- The fixture contains one `invalid_schema` line with source ID, physical line, parser reason, and no decision.
- JSON, Markdown, and `--out` paths are covered by CLI tests.
- No signed-decision verification behavior changed.

## Safety boundary

Report-only. The CLI does not repair evidence, change policy, apply decisions, execute remediation, or self-modify. `automatic_action_taken` remains false.

## Validation

- `python -m pytest -q experiments/test_cage1_review_decision.py experiments/test_cage1_advisory.py` -> 14 passed.
- Broader CAGE-1 fleet/trend/advisory/decision/report regression -> 158 passed.
- Changed modules compile.
- `git diff --check` passes.

## Next priority

Add a deterministic mixed-fleet fixture/report mode containing clean and schema-invalid lines, while preserving both ordinary evidence and critical provenance.
