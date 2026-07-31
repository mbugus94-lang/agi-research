# Build Log - 2026-07-31 - Mixed-Fleet Markdown Evidence Assertion

## Status

Complete. Added a deterministic Markdown regression for the existing mixed-fleet, review-only CAGE-1 fixture. Focused review/advisory tests pass 19/19; the broader CAGE-1 fleet/report/advisory/decision suite passes 138/138.

## Research synthesis

Recent arXiv work on AI research automation, recursive harness improvement, externally grounded evaluation, operational hallucination, and physical long-horizon execution converges on a practical requirement: agent systems need inspectable state, external evidence, and explicit verification boundaries. The build applies that requirement to the CAGE-1 operator report by making valid and schema-invalid fleet evidence visible together with source and physical-line provenance.

## Implementation

- Extended `core/cage1_advisory.py` Markdown output with an evidence-status section when raw fleet lines are present.
- The section counts valid and schema-invalid lines and lists each supported line in input order with source ID, physical line, and the valid decision value.
- Added a CLI regression in `experiments/test_cage1_review_decision.py` for `--fixture mixed-fleet --format markdown`.
- Preserved the review-only boundary: critical findings still require operator review and `automatic_action_taken=False`; no policy, evidence repair, action application, or self-modification occurs.

## Validation

- `python -m pytest -q experiments/test_cage1_review_decision.py experiments/test_cage1_advisory.py` -> **19 passed**.
- Broader CAGE-1 fleet/report/advisory/decision regression -> **138 passed**.
- `python -m py_compile core/cage1_advisory.py cli/cage1_review.py experiments/test_cage1_review_decision.py` passed.
- `git diff --check` passed.
- Manual Markdown output confirmed one valid line and one schema-invalid line remain distinct and ordered.

## Next priority

Add a JSON/Markdown parity check so evidence-status counts cannot diverge between operator surfaces. Keep policy, action application, evidence repair, and self-modification review-gated.

## Sources

- https://arxiv.org/abs/2607.27191v1
- https://arxiv.org/abs/2607.28568v1
- https://arxiv.org/abs/2607.25152v1
- https://arxiv.org/abs/2607.18366v1
- https://arxiv.org/abs/2607.23045v1
- https://github.com/Nanako0129/pilotfish
- https://github.com/PaperBackPear3/microHarnesses
- https://github.com/Pinperepette/context-kernel
- https://github.com/voly-codes/voly
- https://github.com/openai/openai-agents-python/releases/tag/v0.18.3
