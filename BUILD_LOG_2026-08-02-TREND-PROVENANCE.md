# Build Log — 2026-08-02

## Build: mixed valid/schema-invalid trend provenance parity

### Research

The current two-week scan emphasized externally grounded evaluation, reliability-aware memory, executable long-horizon planning, and safety at the skill/tool boundary:

- **OpenSkillRisk** (arXiv:2607.20121v2) reports unsafe actions on roughly 17% of risky third-party-skill cases even in the safest tested configurations. Risk recognition, intervention before acting, and instruction scope remain separate failure points.
- **When Do Agent Loops Mistake Stagnation for Progress?** (arXiv:2607.25152v1) finds that in-band self-evaluation can accept regressions; externally grounded verification is the stronger control.
- **Σ-Mem** (arXiv:2607.27958v1) makes peer reliability and peer relationships explicit, updateable memory rather than treating all agent outputs as equally trustworthy.
- **Stress-testing large language model agents in a robotic chemistry laboratory** (arXiv:2607.23045v1) reports a large gap between plans and executable, constraint-respecting workflows in a physical environment.
- **Can AI agents conduct open-ended AI research?** (arXiv:2607.27191v1) finds that agents can complete engineering tasks but still struggle with research judgment, backtracking, resource awareness, and instruction drift.

Open-source activity signals included `robbyant/lingbot-world-v2` (long-horizon interactive world modeling), `Nanako0129/pilotfish` (bounded multi-model orchestration with verification), `Miguok/fable-harness` (cost-aware routing and adversarial review), and `openai/openai-agents-python` v0.18.3 (session, sandbox, and reliability maintenance). These are activity signals, not a controlled popularity ranking.

### Build

The existing uncommitted regression in `experiments/test_cage1_review_decision.py` was verified and retained as the single build for this run. It adds `test_review_cli_mixed_trend_provenance_is_ordered_and_parity_preserving`, which feeds two ordered trend snapshots containing one valid and one schema-invalid line each through the review CLI in JSON and Markdown modes.

The assertion checks:

- machine-readable evidence counts remain `total=4`, `valid=2`, `invalid_schema=2`, `other=0`;
- snapshot order and source/physical-line provenance remain lossless in the raw trend envelope;
- Markdown emits the same four records in deterministic snapshot/source order;
- valid decisions and schema-invalid records remain distinguishable;
- the path remains review-only: no policy, signed decision, action application, evidence repair, or self-modification is performed.

### Validation

- Focused new regression: **1 passed**.
- Broader CAGE-1 review/advisory/fleet/trend/report regression: **97 passed**.
- `python -m py_compile core/cage1_advisory.py cli/cage1_review.py experiments/test_cage1_review_decision.py` passed.
- `git diff --check` passed.

### Next priority

Add a reusable trend-provenance projection helper or contract test shared by the CLI and advisory layers, while retaining raw evidence and keeping policy, action application, evidence repair, and self-modification review-gated.
