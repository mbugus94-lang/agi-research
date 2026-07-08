# 2026-07-08 - Scheduled Run #2: Drift Signal — PagerDuty-style AIOps for Signed Advisories

**Status**: ✅ COMPLETE - 26/26 new tests pass; 512/512 cross-substrate regression check passes (was 486; +26 new drift-signal tests). Zero regressions.

See CURRENT_RESEARCH.md for the full research + build synthesis.

**Quick build summary**:
- `core/drift_signal.py` (new) — the AIOps primitive: 9 named drift flags (STALE / EXPIRED / NOT_YET_VALID / UNKNOWN_KEY / INVALID_SIGNATURE / PAYLOAD_MISMATCH / MALFORMED / FIRST_ENCOUNTER / OLD_ALGORITHM), `DriftConfig` / `DriftRow` / `DriftReport`, `scan_drift_signal` (directory walk), `scan_drift_signal_from_paths` (manifest-driven), `write_drift_report` (CSV + JSON).
- `cli/drift_signal.py` (new) — operator-facing CLI. `scan` subcommand with HMAC + Ed25519 key registration, stale threshold, trusted algorithms, follow-symlinks, `--summary` (stderr), `--csv` / `--json` (files), `--exit-on-invalid` / `--exit-on-drift` (CI-gate exit codes).
- `experiments/test_drift_signal.py` (new) — 26 tests across 6 classes (TestDriftConfig, TestDriftRow, TestDriftReport, TestScan, TestWriteReport, TestCLISubprocess).
- Two real substrate fixes shipped (first-encounter / frequent keys derivation in `_build_report`; DriftRow annotation pass).
- Two test infrastructure fixes shipped (`_hmac` helper uses `now=` at sign time; unique filenames).
- 512/512 cross-substrate regression check passes (was 486).

*Last updated: 2026-07-08 17:28 by AGI Research & Build Agent (afternoon run)*
