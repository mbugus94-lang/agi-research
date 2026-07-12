"""Tests for the DSCC clearance-mode CLI (cli/dscc_clearance.py).

Smoke + behavior tests for the operator-facing entry point. The CLI
should:
  - Read policies + chain from JSON
  - Read optional clusters + initial classification
  - Honor --mode clearance|taint
  - Emit --summary / --json / default text
  - Exit 0 on PASS, 1 on FAIL, 2 on bad input
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from typing import Dict, List

# Ensure the project root is on sys.path
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from cli.dscc_clearance import main as dscc_main  # noqa: E402
from core.compositional_policy import (  # noqa: E402
    ClassificationLevel,
    CompositionMode,
    DenyReason,
)


def _write_temp_json(name: str, payload: Dict) -> str:
    fd, path = tempfile.mkstemp(suffix=".json", prefix=f"dscc_{name}_")
    with os.fdopen(fd, "w") as f:
        json.dump(payload, f)
    return path


def _safe_unlink(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


class TestDsccClearanceCLI(unittest.TestCase):
    """Smoke + behavior tests for cli/dscc_clearance.py."""

    def setUp(self) -> None:
        # Build a small policy set with mixed classification
        self.policies_payload: Dict[str, Dict] = {
            "read_env": {
                "verb_name": "read_env",
                "taint_in": "internal",
                "classification": "internal",
                "cluster": "data_access",
            },
            "http_post_internal": {
                "verb_name": "http_post_internal",
                "taint_in": "internal",
                "classification": "internal",
                "cluster": "egress",
            },
            "http_post_external": {
                "verb_name": "http_post_external",
                "taint_in": "external",
                "classification": "public",
                "cluster": "egress",
            },
            "read_secret_store": {
                "verb_name": "read_secret_store",
                "taint_in": "secret",
                "classification": "restricted",
                "cluster": "secrets",
            },
        }
        self.policies_path = _write_temp_json("policies", self.policies_payload)
        self.chain_path = _write_temp_json(
            "chain",
            {
                "steps": [
                    {"verb_name": "read_env", "taint_in": "internal"},
                    {"verb_name": "http_post_internal", "taint_in": "internal"},
                ]
            },
        )
        self.bad_chain_path = _write_temp_json(
            "bad_chain",
            {
                "steps": [
                    {"verb_name": "read_env", "taint_in": "internal"},
                    {"verb_name": "http_post_external", "taint_in": "external"},
                    {"verb_name": "read_secret_store", "taint_in": "secret"},
                    {"verb_name": "http_post_external", "taint_in": "external"},
                ]
            },
        )

    def tearDown(self) -> None:
        _safe_unlink(self.policies_path)
        _safe_unlink(self.chain_path)
        _safe_unlink(self.bad_chain_path)

    def _run(self, *argv: str) -> tuple:
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = dscc_main(list(argv))
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 2
        return rc, out.getvalue(), err.getvalue()

    # ---- basic dispatch ----

    def test_help(self) -> None:
        rc, out, _ = self._run("--help")
        # argparse returns 0 on --help
        self.assertEqual(rc, 0)
        self.assertIn("dscc_clearance", out)

    def test_missing_policies(self) -> None:
        rc, _, err = self._run("--chain", self.chain_path)
        self.assertEqual(rc, 2)
        self.assertIn("--policies", err)

    def test_missing_chain(self) -> None:
        rc, _, err = self._run("--policies", self.policies_path)
        self.assertEqual(rc, 2)
        self.assertIn("--chain", err)

    def test_bad_policies_file(self) -> None:
        rc, _, err = self._run(
            "--policies", "/nonexistent.json", "--chain", self.chain_path
        )
        self.assertEqual(rc, 2)
        self.assertIn("cannot read policies", err)

    def test_malformed_chain_json(self) -> None:
        bad = _write_temp_json("bad", {"not_steps": []})
        try:
            rc, _, err = self._run(
                "--policies", self.policies_path, "--chain", bad
            )
            self.assertEqual(rc, 0)  # empty chain -> ALLOW
        finally:
            _safe_unlink(bad)

    # ---- clearance behavior ----

    def test_safe_internal_chain_passes(self) -> None:
        rc, out, _ = self._run(
            "--policies", self.policies_path,
            "--chain", self.chain_path,
            "--summary",
        )
        self.assertEqual(rc, 0)
        self.assertIn("action=allow", out)
        self.assertIn("c_eff=internal", out)

    def test_jadepuffer_blocked_in_clearance_mode(self) -> None:
        rc, out, _ = self._run(
            "--policies", self.policies_path,
            "--chain", self.bad_chain_path,
            "--summary",
        )
        # Bad chain fails clearance: secret read + public egress is
        # blocked either by CLEARANCE_LEVEL_INSUFFICIENT or by
        # SECRET_TO_EXTERNAL. Both produce non-zero exit.
        self.assertEqual(rc, 1)
        # The clearance reason must appear in the summary
        self.assertIn("action=", out)
        # The violation count > 0
        self.assertNotIn("violations=0", out)

    def test_taint_mode_admits_under_classified(self) -> None:
        # In taint mode the clearance check is skipped; the JADEPUFFER
        # chain should still be blocked by SECRET_TO_EXTERNAL though.
        rc, _, _ = self._run(
            "--policies", self.policies_path,
            "--chain", self.bad_chain_path,
            "--mode", "taint",
        )
        # Even in taint mode, SECRET_TO_EXTERNAL still trips.
        self.assertEqual(rc, 1)

    def test_initial_classification(self) -> None:
        rc, out, _ = self._run(
            "--policies", self.policies_path,
            "--chain", self.chain_path,
            "--initial-classification", "confidential",
            "--summary",
        )
        # internal verbs are not cleared to handle confidential data
        self.assertEqual(rc, 1)
        self.assertIn("c_eff=confidential", out)

    # ---- output formats ----

    def test_json_output(self) -> None:
        rc, out, _ = self._run(
            "--policies", self.policies_path,
            "--chain", self.chain_path,
            "--json",
        )
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        self.assertEqual(payload["action"], "allow")
        self.assertEqual(payload["chain_classification"], "internal")
        self.assertEqual(payload["mode"], "clearance")
        self.assertIn("chain_digest", payload)
        self.assertEqual(len(payload["chain_digest"]), 64)  # sha256 hex

    def test_text_output_includes_classification(self) -> None:
        rc, out, _ = self._run(
            "--policies", self.policies_path,
            "--chain", self.chain_path,
        )
        self.assertEqual(rc, 0)
        self.assertIn("Chain C_eff:", out)
        self.assertIn("internal", out)
        self.assertIn("Verdict:", out)

    def test_text_output_includes_violations(self) -> None:
        rc, out, _ = self._run(
            "--policies", self.policies_path,
            "--chain", self.bad_chain_path,
        )
        # The bad chain is blocked; the violation summary should appear
        self.assertEqual(rc, 1)
        self.assertIn("Violations:", out)
        self.assertIn("Verdict:", out)

    def test_clusters_file(self) -> None:
        clusters_payload = {
            "read_env": "data_access",
            "http_post_external": "external_egress",
            "read_secret_store": "secrets",
            "http_post_internal": "data_access",
        }
        clusters_path = _write_temp_json("clusters", clusters_payload)
        try:
            rc, out, _ = self._run(
                "--policies", self.policies_path,
                "--chain", self.bad_chain_path,
                "--clusters", clusters_path,
                "--summary",
            )
            # Distinct clusters (external_egress, secrets) cause
            # CLUSTER_MISMATCH in clearance mode.
            self.assertEqual(rc, 1)
            self.assertIn("violations=", out)
        finally:
            _safe_unlink(clusters_path)

    def test_invalid_mode_raises(self) -> None:
        # argparse-level validation: choices=("clearance", "taint")
        rc, _, err = self._run(
            "--policies", self.policies_path,
            "--chain", self.chain_path,
            "--mode", "bogus",
        )
        self.assertEqual(rc, 2)
        self.assertIn("invalid choice", err)


if __name__ == "__main__":
    unittest.main()
