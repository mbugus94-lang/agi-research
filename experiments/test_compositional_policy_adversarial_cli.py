"""
Adversarial CLI tests for the compositional policy review CLI.

These tests exercise the cli/compositional_review.py surface against
adversarial inputs: malformed JSON, missing files, mixed policy shapes,
chains with unknown verbs, and chains that exercise every deny reason.

Each test runs the CLI as a subprocess (so we exercise the real
entry point) and asserts on the JSON output or exit code.

Run: python -m pytest experiments/test_compositional_policy_adversarial_cli.py -v
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Make sure the project root is importable
sys.path.insert(0, "/home/workspace/agi-research")

REPO_ROOT = Path("/home/workspace/agi-research")
CLI = "cli.compositional_review"


def run_cli(*args, timeout=30):
    """Run the CLI as a subprocess and return (returncode, stdout, stderr).

    Uses `python -m cli.compositional_review` so the CLI runs in the
    same Python environment as the unit tests.
    """
    proc = subprocess.run(
        [sys.executable, "-m", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


# ---------- Helpers ----------

def _write_policies(path, policies):
    with open(path, "w") as f:
        json.dump(policies, f)


def _write_chain(path, steps):
    """CLI expects {"steps": [...]}."""
    with open(path, "w") as f:
        json.dump({"steps": steps}, f)


# Standard policy set covering the JADEPUFFER + safe patterns.
STD_POLICIES = {
    "read_env": {"verb_name": "read_env", "taint_in": "internal", "sinks": ["read"]},
    "read_secret_store": {
        "verb_name": "read_secret_store", "taint_in": "secret",
        "sinks": ["read"], "is_secret_emitting": True,
    },
    "http_get_external": {
        "verb_name": "http_get_external", "taint_in": "external", "sinks": ["egress"]
    },
    "http_post_external": {
        "verb_name": "http_post_external", "taint_in": "external", "sinks": ["egress"]
    },
    "read_file": {
        "verb_name": "read_file", "taint_in": "internal", "sinks": ["read"]
    },
    "write_file": {
        "verb_name": "write_file", "taint_in": "internal", "sinks": ["write"]
    },
    "compute": {
        "verb_name": "compute", "taint_in": "internal", "sinks": ["compute"]
    },
    "exec_cmd": {
        "verb_name": "exec_cmd", "taint_in": "internal", "sinks": ["exec"]
    },
    "log_metric": {
        "verb_name": "log_metric", "taint_in": "internal", "sinks": ["log"]
    },
    "send_email": {
        "verb_name": "send_email", "taint_in": "public", "sinks": ["egress", "public"]
    },
    "http_get": {
        "verb_name": "http_get", "taint_in": "external", "sinks": ["read"]
    },
    "read_user_input": {
        "verb_name": "http_get_external", "taint_in": "external", "sinks": ["read"]
    },
    "sanitize": {
        "verb_name": "sanitize", "taint_in": "internal", "sinks": ["compute"]
    },
    "expense": {
        "verb_name": "expense", "taint_in": "internal", "sinks": ["write"],
        "requires_review": True,
    },
    "render_public": {
        "verb_name": "render_public", "taint_in": "public", "sinks": ["read", "public"]
    },
}


class TestCLISubprocessAdversarial(unittest.TestCase):
    """Adversarial CLI tests. Each test isolates its inputs to a temp dir."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="cpp_adversarial_")
        self.p_path = os.path.join(self.tmpdir, "policies.json")
        self.c_path = os.path.join(self.tmpdir, "chain.json")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # 1. Safe chain -> ALLOW (exit 0)
    # ------------------------------------------------------------------

    def test_cli_safe_chain_returns_allow(self):
        _write_policies(self.p_path, {
            "read_file": {"verb_name": "read_file", "taint_in": "internal",
                          "sinks": ["read"]},
            "summarize": {"verb_name": "summarize", "taint_in": "internal",
                          "sinks": ["compute"]},
        })
        _write_chain(self.c_path, [
            {"verb_name": "read_file", "taint_in": "internal"},
            {"verb_name": "summarize", "taint_in": "internal"},
        ])
        rc, out, err = run_cli(CLI, "--policies", self.p_path, "--chain", self.c_path)
        self.assertEqual(rc, 0, f"stderr={err}\nstdout={out}")
        result = json.loads(out)
        self.assertEqual(result["action"], "allow")
        self.assertEqual(result["reasons"], [])

    # ------------------------------------------------------------------
    # 2. JADEPUFFER pattern -> BLOCK_AND_ESCALATE (exit 3)
    # ------------------------------------------------------------------

    def test_cli_jadepuffer_pattern_blocks_and_escalates(self):
        _write_policies(self.p_path, STD_POLICIES)
        _write_chain(self.c_path, [
            {"verb_name": "read_env", "taint_in": "internal"},
            {"verb_name": "http_get_external", "taint_in": "external"},
            {"verb_name": "read_secret_store", "taint_in": "secret"},
            {"verb_name": "http_post_external", "taint_in": "external"},
        ])
        rc, out, err = run_cli(CLI, "--policies", self.p_path, "--chain", self.c_path)
        self.assertEqual(rc, 3, f"stderr={err}\nstdout={out}")
        result = json.loads(out)
        self.assertEqual(result["action"], "block_and_escalate")
        self.assertIn("secret_to_external", result["reasons"])
        self.assertTrue(result["contains_secret"])

    # ------------------------------------------------------------------
    # 3. Unknown verb -> BLOCK_AND_ESCALATE
    # ------------------------------------------------------------------

    def test_cli_unknown_verb_blocks_and_escalates(self):
        _write_policies(self.p_path, STD_POLICIES)
        _write_chain(self.c_path, [
            {"verb_name": "totally_made_up_verb", "taint_in": "internal"},
        ])
        rc, out, err = run_cli(CLI, "--policies", self.p_path, "--chain", self.c_path)
        self.assertEqual(rc, 3, f"stderr={err}\nstdout={out}")
        result = json.loads(out)
        self.assertIn("unknown_verb", result["reasons"])

    # ------------------------------------------------------------------
    # 4. Write-after-untrusted -> BLOCK
    # ------------------------------------------------------------------

    def test_cli_write_after_untrusted_blocks(self):
        _write_policies(self.p_path, STD_POLICIES)
        _write_chain(self.c_path, [
            {"verb_name": "http_get_external", "taint_in": "external"},
            {"verb_name": "write_file", "taint_in": "internal"},
        ])
        rc, out, err = run_cli(CLI, "--policies", self.p_path, "--chain", self.c_path)
        self.assertEqual(rc, 2, f"stderr={err}\nstdout={out}")
        result = json.loads(out)
        self.assertIn("write_after_untrusted", result["reasons"])

    # ------------------------------------------------------------------
    # 5. Sensitive-to-public (SECRET -> PUBLIC) -> BLOCK
    # ------------------------------------------------------------------

    def test_cli_sensitive_to_public_blocks(self):
        _write_policies(self.p_path, {
            "read_secret_store": {"verb_name": "read_secret_store", "taint_in": "secret",
                                  "sinks": ["read"], "is_secret_emitting": True},
            "render_public": {"verb_name": "render_public", "taint_in": "public",
                              "sinks": ["read", "public"]},
        })
        _write_chain(self.c_path, [
            {"verb_name": "read_secret_store", "taint_in": "secret"},
            {"verb_name": "render_public", "taint_in": "public"},
        ])
        rc, out, err = run_cli(CLI, "--policies", self.p_path, "--chain", self.c_path)
        self.assertEqual(rc, 2, f"stderr={err}\nstdout={out}")
        result = json.loads(out)
        self.assertIn("sensitive_to_public", result["reasons"])

    # ------------------------------------------------------------------
    # 6. Taint escalation -> BLOCK
    # ------------------------------------------------------------------

    def test_cli_taint_escalation_blocks(self):
        # max_taint_threshold=INTERNAL but the step brings in EXTERNAL
        policies = {
            "read_file": {"verb_name": "read_file", "taint_in": "internal",
                          "sinks": ["read"], "max_taint_threshold": "internal"},
            "http_get": {"verb_name": "http_get", "taint_in": "external",
                         "sinks": ["read"]},
        }
        _write_policies(self.p_path, policies)
        _write_chain(self.c_path, [
            {"verb_name": "read_file", "taint_in": "external"},  # above threshold
        ])
        rc, out, err = run_cli(CLI, "--policies", self.p_path, "--chain", self.c_path)
        self.assertEqual(rc, 2, f"stderr={err}\nstdout={out}")
        result = json.loads(out)
        self.assertIn("taint_escalation", result["reasons"])

    # ------------------------------------------------------------------
    # 7. Too many sinks (default max=3) -> ALLOW_ONLY_REVIEW (exit 1)
    # ------------------------------------------------------------------

    def test_cli_too_many_sinks_forces_review(self):
        # The 4 distinct sinks push over the default max_sinks=3
        _write_policies(self.p_path, STD_POLICIES)
        _write_chain(self.c_path, [
            {"verb_name": "read_file", "taint_in": "internal"},     # sink: read
            {"verb_name": "compute", "taint_in": "internal"},       # sink: compute
            {"verb_name": "write_file", "taint_in": "internal"},    # sink: write
            {"verb_name": "exec_cmd", "taint_in": "internal"},      # sink: exec
            {"verb_name": "log_metric", "taint_in": "internal"},    # sink: log
        ])
        rc, out, err = run_cli(CLI, "--policies", self.p_path, "--chain", self.c_path)
        self.assertEqual(rc, 1, f"stderr={err}\nstdout={out}")
        result = json.loads(out)
        self.assertIn("too_many_distinct_sinks", result["reasons"])
        self.assertEqual(result["action"], "allow_only_review")

    # ------------------------------------------------------------------
    # 8. --max-sinks override respected
    # ------------------------------------------------------------------

    def test_cli_too_many_sinks_respects_max_sinks_override(self):
        # With --max-sinks 1, just 2 distinct sinks trips the alarm
        _write_policies(self.p_path, {
            "read_file": {"verb_name": "read_file", "taint_in": "internal",
                          "sinks": ["read"]},
            "write_file": {"verb_name": "write_file", "taint_in": "internal",
                           "sinks": ["write"]},
        })
        _write_chain(self.c_path, [
            {"verb_name": "read_file", "taint_in": "internal"},
            {"verb_name": "write_file", "taint_in": "internal"},
        ])
        rc, out, err = run_cli(CLI, "--policies", self.p_path, "--chain",
                               self.c_path, "--max-sinks", "1")
        self.assertEqual(rc, 1, f"stderr={err}\nstdout={out}")
        result = json.loads(out)
        self.assertIn("too_many_distinct_sinks", result["reasons"])

    # ------------------------------------------------------------------
    # 9. requires_review verb forces ALLOW_ONLY_REVIEW
    # ------------------------------------------------------------------

    def test_cli_requires_review_verb_forces_review(self):
        _write_policies(self.p_path, {
            "expense": {"verb_name": "expense", "taint_in": "internal",
                        "sinks": ["write"], "requires_review": True},
        })
        _write_chain(self.c_path, [
            {"verb_name": "expense", "taint_in": "internal"},
        ])
        rc, out, err = run_cli(CLI, "--policies", self.p_path, "--chain", self.c_path)
        self.assertEqual(rc, 1, f"stderr={err}\nstdout={out}")
        result = json.loads(out)
        self.assertEqual(result["action"], "allow_only_review")

    # ------------------------------------------------------------------
    # 10. Verdict includes taint traces + digest
    # ------------------------------------------------------------------

    def test_cli_verdict_includes_taint_traces(self):
        _write_policies(self.p_path, {
            "read_file": {"verb_name": "read_file", "taint_in": "internal",
                          "sinks": ["read"]},
        })
        _write_chain(self.c_path, [
            {"verb_name": "read_file", "taint_in": "internal"},
        ])
        rc, out, err = run_cli(CLI, "--policies", self.p_path, "--chain", self.c_path)
        self.assertEqual(rc, 0)
        result = json.loads(out)
        self.assertIn("taint_at_each_step", result)
        self.assertIn("sink_taint_at_each_step", result)
        self.assertIn("sinks_seen", result)
        self.assertEqual(result["sinks_seen"], ["read"])
        self.assertEqual(len(result["digest"]), 64)  # sha256 hex

    # ------------------------------------------------------------------
    # 11. Empty chain -> ALLOW
    # ------------------------------------------------------------------

    def test_cli_empty_chain_allows(self):
        _write_policies(self.p_path, STD_POLICIES)
        _write_chain(self.c_path, [])
        rc, out, err = run_cli(CLI, "--policies", self.p_path, "--chain", self.c_path)
        self.assertEqual(rc, 0, f"stderr={err}\nstdout={out}")
        result = json.loads(out)
        self.assertEqual(result["action"], "allow")

    # ------------------------------------------------------------------
    # 12. SECRET -> PUBLIC via email -> BLOCK_AND_ESCALATE (both reasons)
    # ------------------------------------------------------------------

    def test_cli_secret_via_email_blocks(self):
        _write_policies(self.p_path, {
            "read_secret_store": {"verb_name": "read_secret_store", "taint_in": "secret",
                                  "sinks": ["read"], "is_secret_emitting": True},
            "send_email": {"verb_name": "send_email", "taint_in": "public",
                           "sinks": ["egress", "public"]},
        })
        _write_chain(self.c_path, [
            {"verb_name": "read_secret_store", "taint_in": "secret"},
            {"verb_name": "send_email", "taint_in": "public"},
        ])
        rc, out, err = run_cli(CLI, "--policies", self.p_path, "--chain", self.c_path)
        self.assertEqual(rc in (2, 3), True, f"unexpected rc={rc} stderr={err}\nstdout={out}")
        result = json.loads(out)
        # Should at minimum carry sensitive_to_public
        self.assertIn("sensitive_to_public", result["reasons"])

    # ------------------------------------------------------------------
    # 13. Untrusted step then exec -> BLOCK
    # ------------------------------------------------------------------

    def test_cli_untrusted_then_exec_blocks(self):
        _write_policies(self.p_path, {
            "http_get": {"verb_name": "http_get", "taint_in": "external",
                         "sinks": ["read"]},
            "exec_cmd": {"verb_name": "exec_cmd", "taint_in": "internal",
                         "sinks": ["exec"]},
        })
        _write_chain(self.c_path, [
            {"verb_name": "http_get", "taint_in": "external"},
            {"verb_name": "exec_cmd", "taint_in": "internal"},
        ])
        rc, out, err = run_cli(CLI, "--policies", self.p_path, "--chain", self.c_path)
        self.assertEqual(rc, 2, f"stderr={err}\nstdout={out}")
        result = json.loads(out)
        self.assertIn("write_after_untrusted", result["reasons"])

    # ------------------------------------------------------------------
    # 14. Malformed policy file -> nonzero exit
    # ------------------------------------------------------------------

    def test_cli_malformed_policy_file(self):
        with open(self.p_path, "w") as f:
            f.write("{ this is not valid json")
        _write_chain(self.c_path, [])
        rc, out, err = run_cli(CLI, "--policies", self.p_path, "--chain", self.c_path)
        self.assertNotEqual(rc, 0)

    # ------------------------------------------------------------------
    # 15. Missing files -> nonzero exit
    # ------------------------------------------------------------------

    def test_cli_missing_files(self):
        rc, out, err = run_cli(CLI, "--policies", "/nonexistent/policies.json",
                               "--chain", "/nonexistent/chain.json")
        self.assertNotEqual(rc, 0)

    # ------------------------------------------------------------------
    # 16. --summary outputs human-readable on stderr
    # ------------------------------------------------------------------

    def test_cli_summary_outputs_human_readable(self):
        _write_policies(self.p_path, {
            "read_file": {"verb_name": "read_file", "taint_in": "internal",
                          "sinks": ["read"]},
        })
        _write_chain(self.c_path, [
            {"verb_name": "read_file", "taint_in": "internal"},
        ])
        rc, out, err = run_cli(CLI, "--policies", self.p_path, "--chain",
                               self.c_path, "--summary")
        self.assertEqual(rc, 0)
        # JSON is on stdout
        json.loads(out)
        # Summary text is on stderr
        self.assertIn("verdict:", err.lower())

    # ------------------------------------------------------------------
    # 17. Determinism: same input -> same digest across two runs
    # ------------------------------------------------------------------

    def test_cli_determinism_across_runs(self):
        _write_policies(self.p_path, {
            "read_file": {"verb_name": "read_file", "taint_in": "internal",
                          "sinks": ["read"]},
            "compute": {"verb_name": "compute", "taint_in": "internal",
                        "sinks": ["compute"]},
        })
        _write_chain(self.c_path, [
            {"verb_name": "read_file", "taint_in": "internal"},
            {"verb_name": "compute", "taint_in": "internal"},
        ])
        rc1, out1, _ = run_cli(CLI, "--policies", self.p_path, "--chain", self.c_path)
        rc2, out2, _ = run_cli(CLI, "--policies", self.p_path, "--chain", self.c_path)
        self.assertEqual(rc1, rc2)
        self.assertEqual(json.loads(out1)["digest"], json.loads(out2)["digest"])


if __name__ == "__main__":
    unittest.main()
