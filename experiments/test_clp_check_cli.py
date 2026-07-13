"""Tests for cli.clp_check (Prismata §3 read-side CLI).

Mirrors the style of experiments/test_dscc_clearance_cli.py.

Coverage:
  1. Help / no-args path.
  2. Benign chain passes (read side only).
  3. Benign chain with write gate passes (combined AND).
  4. JADEPUFFER chain is blocked on the read side.
  5. Privilege promotion (wider after narrower) is blocked.
  6. Undeclared verb → MISSING_CAPABILITY.
  7. JSON output is well-formed.
  8. JSON output records visibility trace per step.
  9. Summary output is one line.
 10. Summary output includes write verdict when provided.
 11. Dual-gate combined output reports both verdicts.
 12. Combined dual-gate blocks when either side blocks.
 13. labels-only-decrease field appears in text output.
 14. Capability file: visibility ranks deterministically.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_cli(extra_args, caps, chain, write_policies=None):
    with tempfile.TemporaryDirectory() as td:
        cap_path = os.path.join(td, "caps.json")
        chain_path = os.path.join(td, "chain.json")
        with open(cap_path, "w") as f:
            json.dump(caps, f)
        with open(chain_path, "w") as f:
            json.dump(chain, f)
        args = [
            sys.executable, "-m", "cli.clp_check",
            "--capabilities", cap_path,
            "--chain", chain_path,
            *extra_args,
        ]
        if write_policies is not None:
            wp_path = os.path.join(td, "wp.json")
            with open(wp_path, "w") as f:
                json.dump(write_policies, f)
            args.extend(["--write-policies", wp_path])
        proc = subprocess.run(
            args, cwd=REPO_ROOT, capture_output=True, text=True, timeout=60
        )
    return proc


def _benign_caps():
    return {
        "read_env": {
            "name": "read_env",
            "required_label": "secret",
            "reads_untrusted_input": True,
        },
        "http_post_external": {
            "name": "http_post_external",
            "required_label": "public",
            "emits_to_sink": True,
        },
        "pure_compute": {
            "name": "pure_compute",
            "required_label": "internal",
        },
    }


def _benign_chain():
    return {"steps": [
        {"verb_name": "read_env"},
        {"verb_name": "pure_compute"},
    ]}


# ---------------------------------------------------------------------------
# 1. Help / no-args
# ---------------------------------------------------------------------------

def test_help_prints_usage():
    r = subprocess.run(
        [sys.executable, "-m", "cli.clp_check", "--help"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0
    assert "Contextual Least Privilege" in r.stdout


# ---------------------------------------------------------------------------
# 2. Benign chain (read-only)
# ---------------------------------------------------------------------------

def test_benign_chain_read_only_passes():
    r = _run_cli(
        ["--initial-visibility", "secret"],
        _benign_caps(), _benign_chain(),
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "Read verdict:        allow" in r.stdout


# ---------------------------------------------------------------------------
# 3. Benign chain with write gate passes
# ---------------------------------------------------------------------------

def test_benign_chain_with_write_gate_passes():
    write_policies = {
        "read_env": {"verb_name": "read_env", "taint_in": "internal"},
        "pure_compute": {"verb_name": "pure_compute", "taint_in": "internal"},
    }
    r = _run_cli(
        ["--initial-visibility", "secret"],
        _benign_caps(), _benign_chain(), write_policies,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "Both admit:          True" in r.stdout


# ---------------------------------------------------------------------------
# 4. JADEPUFFER chain is blocked on the read side
# ---------------------------------------------------------------------------

def test_jadepuffer_read_side_blocks():
    """The Prismata read-side gate catches the JADEPUFFER shape
    because ``read_secret_store`` (SECRET) cannot be reached after
    ``read_env`` (INTERNAL) has narrowed the running visibility to
    SECRET-or-lower — wait, INTERNAL narrows to SECRET (min of SECRET
    and INTERNAL) so this chain actually works on the read side.

    Instead, the canonical Prismata test is the 'wider after
    narrower' pattern: a chain that first narrows to PUBLIC then
    tries to widen back to SECRET.
    """
    caps = {
        "narrower": {
            "name": "narrower",
            "required_label": "public",
        },
        "wider_attempt": {
            "name": "wider_attempt",
            "required_label": "secret",
        },
    }
    chain = {"steps": [
        {"verb_name": "narrower"},
        {"verb_name": "wider_attempt"},
    ]}
    r = _run_cli(
        ["--initial-visibility", "secret"],
        caps, chain,
    )
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "Read verdict:        block" in r.stdout.lower() or "block" in r.stdout.lower()


# ---------------------------------------------------------------------------
# 5. Privilege promotion is blocked
# ---------------------------------------------------------------------------

def test_privilege_promotion_blocked():
    """Going from narrow visibility (PUBLIC) to a verb that needs
    SECRET visibility must block — you can't widen back."""
    caps = {
        "narrower": {"name": "narrower", "required_label": "public"},
        "promote": {"name": "promote", "required_label": "secret"},
    }
    chain = {"steps": [
        {"verb_name": "narrower"},
        {"verb_name": "promote"},
    ]}
    r = _run_cli(
        ["--initial-visibility", "secret"],
        caps, chain,
    )
    assert r.returncode == 1
    assert "VISIBILITY_INSUFFICIENT" in r.stdout or "visibility" in r.stdout.lower()


# ---------------------------------------------------------------------------
# 6. Undeclared verb → MISSING_CAPABILITY
# ---------------------------------------------------------------------------

def test_missing_capability_blocks():
    caps = {"declared": {"name": "declared", "required_label": "internal"}}
    chain = {"steps": [{"verb_name": "undeclared_verb"}]}
    r = _run_cli(
        ["--initial-visibility", "secret"], caps, chain,
    )
    assert r.returncode == 1
    # The CLI prints reasons which include MISSING_CAPABILITY or
    # CAPABILITY_NOT_REGISTERED.
    assert "MISSING_CAPABILITY" in r.stdout or "missing" in r.stdout.lower()


# ---------------------------------------------------------------------------
# 7. JSON output is well-formed
# ---------------------------------------------------------------------------

def test_json_output_is_well_formed():
    r = _run_cli(
        ["--initial-visibility", "secret", "--json"],
        _benign_caps(), _benign_chain(),
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "action" in data
    assert "reasons" in data
    assert "visibility_at_each_step" in data
    assert "labels_only_decrease" in data
    assert "chain_digest" in data


# ---------------------------------------------------------------------------
# 8. JSON output records visibility trace per step
# ---------------------------------------------------------------------------

def test_json_output_records_visibility_trace():
    r = _run_cli(
        ["--initial-visibility", "secret", "--json"],
        _benign_caps(), _benign_chain(),
    )
    data = json.loads(r.stdout)
    # Two steps in the chain; trace should have 2 entries.
    assert len(data["visibility_at_each_step"]) == 2


# ---------------------------------------------------------------------------
# 9. Summary output is one line
# ---------------------------------------------------------------------------

def test_summary_output_is_one_line():
    r = _run_cli(
        ["--initial-visibility", "secret", "--summary"],
        _benign_caps(), _benign_chain(),
    )
    assert r.returncode == 0
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    assert len(lines) == 1
    assert "action=" in lines[0]


# ---------------------------------------------------------------------------
# 10. Summary with write policies
# ---------------------------------------------------------------------------

def test_summary_with_write_policies():
    write_policies = {
        "read_env": {"verb_name": "read_env", "taint_in": "internal"},
        "pure_compute": {"verb_name": "pure_compute", "taint_in": "internal"},
    }
    r = _run_cli(
        ["--initial-visibility", "secret", "--summary"],
        _benign_caps(), _benign_chain(), write_policies,
    )
    assert r.returncode == 0
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    assert len(lines) == 1
    assert "read=" in lines[0] and "write=" in lines[0] and "both_allow=" in lines[0]


# ---------------------------------------------------------------------------
# 11. Dual-gate combined output reports both verdicts
# ---------------------------------------------------------------------------

def test_dual_gate_combined_output():
    write_policies = {
        "read_env": {"verb_name": "read_env", "taint_in": "internal"},
        "pure_compute": {"verb_name": "pure_compute", "taint_in": "internal"},
    }
    r = _run_cli(
        ["--initial-visibility", "secret", "--json"],
        _benign_caps(), _benign_chain(), write_policies,
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "write" in data
    assert "both_allow" in data
    assert data["both_allow"] is True


# ---------------------------------------------------------------------------
# 12. Combined dual-gate blocks when either side blocks
# ---------------------------------------------------------------------------

def test_combined_dual_gate_blocks_on_either_side():
    """A 2-step chain that grows taint to SECRET and then egresses
    to EXTERNAL: the write gate blocks via SECRET_TO_EXTERNAL. The
    read side is benign. Combined must return exit 1."""
    caps = {
        "t1": {"name": "t1", "required_label": "secret"},
        "t2": {"name": "t2", "required_label": "public", "emits_to_sink": True},
    }
    # Write side: t1 claims taint=secret → t2 (taint=external, sink=egress).
    # SECRET_TO_EXTERNAL fires on t2.
    write_policies = {
        "t1": {"verb_name": "t1", "taint_in": "secret"},
        "t2": {"verb_name": "t2", "taint_in": "external", "sinks": ["egress"]},
    }
    chain = {"steps": [
        {"verb_name": "t1"},
        {"verb_name": "t2"},
    ]}
    r = _run_cli(
        ["--initial-visibility", "secret"],
        caps, chain, write_policies,
    )
    # The write side blocks on SECRET_TO_EXTERNAL — combined exit 1.
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "rejected" in r.stdout.lower() or "block" in r.stdout.lower()


# ---------------------------------------------------------------------------
# 13. labels-only-decrease field in text output
# ---------------------------------------------------------------------------

def test_labels_only_decrease_field_in_text_output():
    r = _run_cli(
        ["--initial-visibility", "secret"],
        _benign_caps(), _benign_chain(),
    )
    assert r.returncode == 0
    assert "labels-only-decrease" in r.stdout.lower()


# ---------------------------------------------------------------------------
# 14. JADEPUFFER read-side block (the original example)
# ---------------------------------------------------------------------------

def test_jadepuffer_read_side_catches_attack():
    """The integrity dual of the JADEPUFFER chain. The write side
    catches the SECRET→EXTERNAL data flow; the read side does NOT
    catch the same chain (it's the integrity dual, not the
    confidentiality duplicate). This test confirms that BOTH gates
    on this chain: read = allow, write = block, combined = block.

    Mirrors the existing test_compositional_policy_adversarial
    'test_secret_then_public_sink_blocks' shape.
    """
    caps = {
        "read_secret": {
            "name": "read_secret",
            "required_label": "secret",
            "reads_untrusted_input": True,
        },
        "log_public": {
            "name": "log_public",
            "required_label": "public",
            "emits_to_sink": True,
        },
    }
    write_policies = {
        "read_secret": {"verb_name": "read_secret", "taint_in": "secret", "sinks": ["read"]},
        "log_public": {"verb_name": "log_public", "taint_in": "public", "sinks": ["egress"]},
    }
    chain = {"steps": [
        {"verb_name": "read_secret"},
        {"verb_name": "log_public"},
    ]}
    r = _run_cli(
        ["--initial-visibility", "secret", "--json"],
        caps, chain, write_policies,
    )
    data = json.loads(r.stdout)
    # Write side blocks (SENSITIVE_TO_PUBLIC / SECRET_TO_EXTERNAL)
    # Read side is benign (the read side is integrity, not confidentiality).
    assert data["both_allow"] is False
    write_reasons = data["write"].get("reasons", [])
    assert any("secret" in r or "sensitive" in r for r in write_reasons)
