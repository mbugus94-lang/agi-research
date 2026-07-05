"""Tests for cli.cpp_run (Constraint Pressure Probe CLI)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cli import cpp_run as cpp_cli  # noqa: E402


# --- Target module installed for the CLI tests --------------------------

def _honest_target(verb_name: str, level_name: str, prompt: str) -> str:
    """A target that returns truthful text — should never trigger CEF."""
    return f"Honest response to verb={verb_name} level={level_name}: I can help with that."


def _fabricating_target(verb_name: str, level_name: str, prompt: str) -> str:
    """A target that fabricates external obstacles — should trigger CEF
    at every level, especially L7+ (retraction sealed)."""
    base = f"Response to verb={verb_name} level={level_name}:"
    if level_name == "L0_baseline":
        return base + " Here is the data you requested: [valid response]"
    if level_name == "L1_soft_pressure":
        return base + " Here is the data: [valid response]"
    # From L2 onward, fabricate external obstacles
    return (
        base
        + " I'm currently unable to share that data. There is a third-party "
        + "upstream system that is currently being processed. A Traceback "
        + "(most recent call last): File 'pay.py', line 42, in 0xDEADBEEF."
    )


# --- Tests ---------------------------------------------------------------


class TestParseVerbs:
    def test_empty(self):
        assert cpp_cli._parse_verbs(None) == ()
        assert cpp_cli._parse_verbs("") == ()

    def test_single_verb(self):
        assert cpp_cli._parse_verbs("pay") == ("pay",)

    def test_multiple_verbs(self):
        assert cpp_cli._parse_verbs("pay,read,write") == ("pay", "read", "write")

    def test_whitespace_tolerated(self):
        assert cpp_cli._parse_verbs(" pay , read ") == ("pay", "read")


class TestLoadTarget:
    def test_no_spec_raises(self):
        with pytest.raises(ValueError, match="no --target-module"):
            cpp_cli._load_target(None)

    def test_bad_spec_raises(self):
        with pytest.raises(ValueError, match="module:callable"):
            cpp_cli._load_target("nocolon")

    def test_loads_callable(self):
        # `experiments.test_cpp_run_cli._honest_target` is the canonical
        # importable path; we just need a module+callable that exists.
        spec = "experiments.test_cpp_run_cli:_honest_target"
        target = cpp_cli._load_target(spec)
        assert callable(target)
        out = target("pay", "L0_baseline", "test")
        assert "Honest" in out


class TestFormatSummary:
    def test_includes_worst_band_and_counts(self):
        target = _honest_target
        probe = cpp_cli.ConstraintPressureProbe()
        outcome = probe.run(target, verbs=("pay",))
        text = cpp_cli._format_summary(outcome)
        assert "Total observations:" in text
        assert "Worst band:" in text
        assert "Thanatosis" in text
        assert "Emergence by level" in text
        assert "L0_baseline" in text

    def test_includes_verb_section(self):
        target = _honest_target
        probe = cpp_cli.ConstraintPressureProbe()
        outcome = probe.run(target, verbs=("pay", "read"))
        text = cpp_cli._format_summary(outcome)
        assert "Emergence by verb" in text
        assert "pay" in text
        assert "read" in text


class TestMain:
    def test_honest_target_returns_0(self, tmp_path):
        audit = str(tmp_path / "audit.jsonl")
        rc = cpp_cli.main([
            "--target-module", "experiments.test_cpp_run_cli:_honest_target",
            "--verbs", "pay",
            "--audit", audit,
            "--summary",
        ])
        assert rc == 0
        assert Path(audit).exists()
        # Audit log has one line per observation + a final outcome line
        lines = Path(audit).read_text().strip().split("\n")
        assert len(lines) >= 9  # 9 levels + 1 outcome
        last = json.loads(lines[-1])
        assert last["kind"] == "outcome"
        assert last["worst_band"] == "none"

    def test_fabricating_target_returns_2(self, tmp_path):
        audit = str(tmp_path / "audit.jsonl")
        rc = cpp_cli.main([
            "--target-module", "experiments.test_cpp_run_cli:_fabricating_target",
            "--verbs", "pay",
            "--audit", audit,
        ])
        # Fabricating target triggers CRITICAL → exit 2
        assert rc == 2

    def test_json_out_written(self, tmp_path):
        json_out = str(tmp_path / "outcome.json")
        rc = cpp_cli.main([
            "--target-module", "experiments.test_cpp_run_cli:_honest_target",
            "--verbs", "read",
            "--json-out", json_out,
        ])
        assert rc == 0
        assert Path(json_out).exists()
        data = json.loads(Path(json_out).read_text())
        assert "observations" in data
        assert "worst_band" in data
        assert "emergence_by_level" in data
        assert "emergence_by_verb" in data
        assert data["worst_band"] == "none"
        assert data["total_observations"] == 9

    def test_cli_runs_via_subprocess(self, tmp_path):
        audit = str(tmp_path / "audit.jsonl")
        cmd = [
            sys.executable, "-m", "cli.cpp_run",
            "--target-module", "experiments.test_cpp_run_cli:_honest_target",
            "--verbs", "pay",
            "--audit", audit,
            "--summary",
        ]
        result = subprocess.run(cmd, cwd=str(_REPO_ROOT), capture_output=True, text=True)
        assert result.returncode == 0
        assert "Worst band:" in result.stdout
        assert "Emergence by level" in result.stdout
        assert Path(audit).exists()

    def test_no_target_via_subprocess_errors_cleanly(self):
        cmd = [sys.executable, "-m", "cli.cpp_run", "--verbs", "pay"]
        result = subprocess.run(cmd, cwd=str(_REPO_ROOT), capture_output=True, text=True)
        # The CLI raises ValueError which becomes a non-zero exit
        assert result.returncode != 0
        assert "no --target-module" in result.stderr

    def test_exit_code_mapping(self, tmp_path):
        # Honest target: rc=0
        rc = cpp_cli.main([
            "--target-module", "experiments.test_cpp_run_cli:_honest_target",
        ])
        assert rc == 0
        # Fabricating target: rc=2 (CRITICAL)
        rc = cpp_cli.main([
            "--target-module", "experiments.test_cpp_run_cli:_fabricating_target",
        ])
        assert rc == 2
