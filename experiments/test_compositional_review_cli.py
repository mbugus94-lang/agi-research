"""Tests for the compositional_review CLI (cli/compositional_review.py)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _run_cli(policies_path, chain_path, *extra):
    return subprocess.run(
        [
            sys.executable, "-m", "cli.compositional_review",
            "--policies", str(policies_path),
            "--chain", str(chain_path),
            *extra,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )


SAFE_POLICIES = {
    "read_env": {"verb_name": "read_env", "taint_in": "internal", "sinks": ["read"]},
    "http_get_external": {"verb_name": "http_get_external", "taint_in": "external", "sinks": ["egress"]},
    "read_secret_store": {
        "verb_name": "read_secret_store",
        "taint_in": "secret",
        "sinks": ["read"],
        "is_secret_emitting": True,
    },
    "http_post_external": {
        "verb_name": "http_post_external",
        "taint_in": "external",
        "sinks": ["egress"],
    },
    "compute": {"verb_name": "compute", "taint_in": "internal", "sinks": ["read"]},
}


def _write_chain(steps):
    return {"steps": steps}


class TestCLIBasic(unittest.TestCase):
    def test_jadepuffer_block_and_escalate(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "p.json"
            c = Path(td) / "c.json"
            p.write_text(json.dumps(SAFE_POLICIES))
            c.write_text(json.dumps(_write_chain([
                {"verb_name": "read_env", "taint_in": "internal"},
                {"verb_name": "http_get_external", "taint_in": "external"},
                {"verb_name": "read_secret_store", "taint_in": "secret"},
                {"verb_name": "http_post_external", "taint_in": "external"},
            ])))
            r = _run_cli(p, c, "--summary")
            self.assertEqual(r.returncode, 3)  # BLOCK_AND_ESCALATE
            self.assertIn("secret_to_external", r.stdout)
            self.assertIn("block_and_escalate", r.stdout)

    def test_safe_chain_allow(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "p.json"
            c = Path(td) / "c.json"
            p.write_text(json.dumps(SAFE_POLICIES))
            c.write_text(json.dumps(_write_chain([
                {"verb_name": "read_env", "taint_in": "internal"},
                {"verb_name": "compute", "taint_in": "internal"},
            ])))
            r = _run_cli(p, c, "--summary")
            self.assertEqual(r.returncode, 0)  # ALLOW
            self.assertIn("allow", r.stdout)

    def test_unknown_verb_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "p.json"
            c = Path(td) / "c.json"
            p.write_text(json.dumps(SAFE_POLICIES))
            c.write_text(json.dumps(_write_chain([
                {"verb_name": "unknown_verb", "taint_in": "internal"},
            ])))
            r = _run_cli(p, c)
            self.assertEqual(r.returncode, 3)  # BLOCK_AND_ESCALATE
            payload = json.loads(r.stdout)
            self.assertIn("unknown_verb", payload["reasons"])

    def test_summary_flag_human_readable(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "p.json"
            c = Path(td) / "c.json"
            p.write_text(json.dumps(SAFE_POLICIES))
            c.write_text(json.dumps(_write_chain([
                {"verb_name": "read_env", "taint_in": "internal"},
            ])))
            r = _run_cli(p, c, "--summary")
            self.assertIn("verdict:", r.stderr)
            self.assertIn("digest:", r.stderr)

    def test_exit_code_allow(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "p.json"
            c = Path(td) / "c.json"
            p.write_text(json.dumps(SAFE_POLICIES))
            c.write_text(json.dumps(_write_chain([
                {"verb_name": "read_env", "taint_in": "internal"},
            ])))
            r = _run_cli(p, c)
            self.assertEqual(r.returncode, 0)

    def test_exit_code_block_only(self):
        # write-after-untrusted: BLOCK (2)
        policies = {
            "fetch": {"verb_name": "fetch", "taint_in": "external", "sinks": ["egress"]},
            "write": {"verb_name": "write", "taint_in": "internal", "sinks": ["write"]},
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "p.json"
            c = Path(td) / "c.json"
            p.write_text(json.dumps(policies))
            c.write_text(json.dumps(_write_chain([
                {"verb_name": "fetch", "taint_in": "untrusted"},
                {"verb_name": "write", "taint_in": "internal"},
            ])))
            r = _run_cli(p, c)
            self.assertEqual(r.returncode, 2)  # BLOCK

    def test_exit_code_allow_only_review(self):
        policies = {
            "fetch": {"verb_name": "fetch", "taint_in": "external", "sinks": ["egress", "read", "write", "exec"]},
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "p.json"
            c = Path(td) / "c.json"
            p.write_text(json.dumps(policies))
            c.write_text(json.dumps(_write_chain([
                {"verb_name": "fetch", "taint_in": "external"},
            ])))
            r = _run_cli(p, c)
            # 4 distinct sinks (egress, read, write, exec) > 3 -> ALLOW_ONLY_REVIEW
            self.assertEqual(r.returncode, 1)

    def test_invalid_policies_file_errors(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "p.json"
            c = Path(td) / "c.json"
            p.write_text("not json")
            c.write_text(json.dumps(_write_chain([])))
            r = _run_cli(p, c)
            self.assertNotEqual(r.returncode, 0)

    def test_missing_chain_file_errors(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "p.json"
            c = Path(td) / "c.json"
            p.write_text(json.dumps(SAFE_POLICIES))
            # c does not exist
            r = _run_cli(p, c)
            self.assertNotEqual(r.returncode, 0)

    def test_json_output_is_valid_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "p.json"
            c = Path(td) / "c.json"
            p.write_text(json.dumps(SAFE_POLICIES))
            c.write_text(json.dumps(_write_chain([
                {"verb_name": "read_env", "taint_in": "internal"},
            ])))
            r = _run_cli(p, c)
            payload = json.loads(r.stdout)
            self.assertIn("action", payload)
            self.assertIn("digest", payload)


if __name__ == "__main__":
    unittest.main()
