"""Tests for cli/aibom_review.py.

The CLI is the operator-facing surface for the AIBOM advisory emitter
(arXiv:2606.19390). It reads a CPP JSONL audit log + an optional
bundle snapshot, emits a self-contained AIBOMAdvisory JSON, and
prints a human-readable summary.

Test coverage (16 tests across 6 test classes):
  - TestFormatHelpers (3): _format_summary, _format_advisory_table
  - TestLoadBundleSnapshot (3): missing path, missing file, valid JSON
  - TestMainMissingAuditLog (2): --audit-log missing, --help works
  - TestMainSummary (2): clean audit log, CEF audit log
  - TestMainJsonOut (2): --out writes file, --out + --silent no stdout
  - TestSubprocess (4): clean run, CEF run, --summary, --out
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

from cli import aibom_review
from cli.aibom_review import (
    _format_advisory_table,
    _format_summary,
    _load_bundle_snapshot,
    main,
)
from core.aibom_advisory import (
    AdvisoryCategory,
    AdvisorySeverity,
    AdvisoryStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_audit_log(
    path: Path,
    records: List[Dict[str, Any]],
) -> Path:
    """Write records to a JSONL file at path."""
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return path


def _obs(
    *,
    verb_name: str = "pay",
    cef_type: str = None,
    severity: str = None,
    marker_count: int = 0,
    band: str = "none",
    level_index: int = 0,
    level_name: str = "L0_baseline",
    policy_source: str = None,
) -> Dict[str, Any]:
    return {
        "level_index": level_index,
        "level_name": level_name,
        "kind": "exit_sealing",
        "verb_name": verb_name,
        "sealed_exits": [],
        "prompt_hash": "phash",
        "output_hash": "ohash",
        "output_length": 50,
        "detection": None,
        "cef_type": cef_type,
        "severity": severity,
        "marker_count": marker_count,
        "recommended_action": None,
        "band": band,
        "observed_at": 0.0,
        "elapsed_ms": 1.0,
        "policy_resolution": None,
        "policy_source": policy_source,
    }


# ---------------------------------------------------------------------------
# TestFormatHelpers
# ---------------------------------------------------------------------------


class TestFormatHelpers:
    def test_format_summary_contains_advisory_id(self):
        from core.aibom_advisory import AIBOMAdvisory

        adv = AIBOMAdvisory(
            document={"title": "t", "publisher": "p"},
            product_tree={"components": []},
            vulnerabilities=[],
            notes=[],
            references=[],
            advisory_id="d" * 64,
            category="generic",
            severity="none",
            recommendation="defer",
            status="interim",
            generated_at=0.0,
            evidence_digest="e" * 64,
            bundle_library_id=None,
            audit_log_path=None,
            cef_substrate_available=False,
            total_observations=0,
            thanatosis_count=0,
            worst_band="none",
            component_count=0,
        )
        s = _format_summary(adv)
        assert "AIBOM Advisory" in s
        assert ("d" * 16) in s
        assert "severity" in s
        assert "category" in s

    def test_format_advisory_table_empty(self):
        from core.aibom_advisory import AIBOMAdvisory

        adv = AIBOMAdvisory(
            document={}, product_tree={"components": []}, vulnerabilities=[],
            notes=[], references=[],
            advisory_id="x", category="generic", severity="none",
            recommendation="defer", status="interim", generated_at=0.0,
            evidence_digest="", bundle_library_id=None, audit_log_path=None,
            cef_substrate_available=False, total_observations=0,
            thanatosis_count=0, worst_band="none", component_count=0,
        )
        t = _format_advisory_table(adv)
        assert "component" in t
        assert "exploitability" in t

    def test_format_advisory_table_with_components(self):
        from core.aibom_advisory import AIBOMAdvisory

        adv = AIBOMAdvisory(
            document={},
            product_tree={"components": [{
                "component_id": "pay@v1",
                "verb_name": "pay",
                "verb_version": "v1",
                "policy_source": "specific",
                "policy_digest": "d" * 64,
                "policy_rationale": "test",
                "exploitability": "high",
                "observed_severity": "high",
                "observed_band": "high",
                "observed_marker_count": 4,
                "observed_cef_type": "external_obstacle",
                "observation_count": 1,
                "thanatosis_count": 0,
                "worst_level_index": 5,
                "worst_level_name": "L5_data_removed",
                "recommendation": "remediate",
                "status": "known_affected",
                "notes": [],
            }]},
            vulnerabilities=[], notes=[], references=[],
            advisory_id="x", category="cef_emergence", severity="high",
            recommendation="remediate", status="interim", generated_at=0.0,
            evidence_digest="", bundle_library_id=None, audit_log_path=None,
            cef_substrate_available=True, total_observations=1,
            thanatosis_count=0, worst_band="high", component_count=1,
        )
        t = _format_advisory_table(adv)
        assert "pay@v1" in t
        assert "high" in t


# ---------------------------------------------------------------------------
# TestLoadBundleSnapshot
# ---------------------------------------------------------------------------


class TestLoadBundleSnapshot:
    def test_load_bundle_snapshot_no_path(self):
        assert _load_bundle_snapshot(None) is None
        assert _load_bundle_snapshot("") is None

    def test_load_bundle_snapshot_missing_file(self, tmp_path: Path):
        assert _load_bundle_snapshot(str(tmp_path / "missing.json")) is None

    def test_load_bundle_snapshot_valid(self, tmp_path: Path):
        p = tmp_path / "bundle.json"
        payload = {"library_id": "x", "entries": {}}
        p.write_text(json.dumps(payload))
        loaded = _load_bundle_snapshot(str(p))
        assert loaded == payload

    def test_load_bundle_snapshot_malformed(self, tmp_path: Path):
        p = tmp_path / "bundle.json"
        p.write_text("not json {")
        assert _load_bundle_snapshot(str(p)) is None


# ---------------------------------------------------------------------------
# TestMainMissingAuditLog
# ---------------------------------------------------------------------------


class TestMainMissingAuditLog:
    def test_main_missing_audit_log_arg(self, capsys):
        # No --audit-log: SystemExit 2 from argparse
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 2

    def test_main_help(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["--help"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "AIBOM" in out
        assert "--audit-log" in out


# ---------------------------------------------------------------------------
# TestMainSummary
# ---------------------------------------------------------------------------


class TestMainSummary:
    def test_clean_audit_log_summary(self, tmp_path: Path, capsys):
        # --summary prints, --silent does not. Use --summary alone.
        audit = _write_audit_log(tmp_path / "cpp.jsonl", [_obs()])
        rc = main(["--audit-log", str(audit), "--summary"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "AIBOM Advisory" in out
        assert "category:" in out

    def test_cef_audit_log_summary(self, tmp_path: Path, capsys):
        audit = _write_audit_log(tmp_path / "cpp.jsonl", [
            _obs(cef_type="external_obstacle", severity="high", band="high",
                 marker_count=3, level_index=5, level_name="L5_data_removed"),
        ])
        rc = main(["--audit-log", str(audit), "--summary"])
        out = capsys.readouterr().out
        assert rc == 1  # REMEDIATE
        assert "severity:" in out
        assert "high" in out
        assert "remediate" in out

    def test_thanatosis_audit_log_blocks(self, tmp_path: Path, capsys):
        audit = _write_audit_log(tmp_path / "cpp.jsonl", [
            _obs(cef_type="simulated_crash", severity="critical", band="critical",
                 marker_count=4, level_index=7, level_name="L7_retraction_sealed"),
        ])
        rc = main(["--audit-log", str(audit), "--summary"])
        assert rc == 2  # BLOCK
        out = capsys.readouterr().out
        assert "thanatosis_count" in out

    def test_with_bundle_snapshot(self, tmp_path: Path, capsys):
        audit = _write_audit_log(tmp_path / "cpp.jsonl", [
            _obs(cef_type="external_obstacle", severity="medium", band="medium",
                 marker_count=2, level_index=3, level_name="L3_repeated_denial"),
        ])
        bundle = tmp_path / "bundle.json"
        bundle.write_text(json.dumps({
            "library_id": "test-bundle",
            "default_config": {"severity_to_action": "log"},
            "entries": {},
        }))
        rc = main(["--audit-log", str(audit), "--bundle-snapshot", str(bundle),
                   "--summary"])
        out = capsys.readouterr().out
        assert rc == 0  # MEDIUM -> MONITOR
        assert "test-bundle" in out


# ---------------------------------------------------------------------------
# TestMainJsonOut
# ---------------------------------------------------------------------------


class TestMainJsonOut:
    def test_out_writes_file(self, tmp_path: Path, capsys):
        audit = _write_audit_log(tmp_path / "cpp.jsonl", [_obs()])
        out = tmp_path / "advisory.json"
        rc = main(["--audit-log", str(audit), "--out", str(out), "--silent"])
        assert rc == 0
        assert out.exists()
        loaded = json.loads(out.read_text())
        assert "advisory_id" in loaded
        assert "category" in loaded
        assert "severity" in loaded

    def test_out_and_silent_no_stdout(self, tmp_path: Path, capsys):
        audit = _write_audit_log(tmp_path / "cpp.jsonl", [_obs()])
        out = tmp_path / "advisory.json"
        rc = main(["--audit-log", str(audit), "--out", str(out), "--silent"])
        out_capture = capsys.readouterr().out
        assert rc == 0
        assert out_capture == ""

    def test_out_dumps_to_stdout_when_no_summary(self, tmp_path: Path, capsys):
        audit = _write_audit_log(tmp_path / "cpp.jsonl", [_obs()])
        out = tmp_path / "advisory.json"
        rc = main(["--audit-log", str(audit), "--out", str(out)])
        out_capture = capsys.readouterr().out
        # Without --summary, the JSON is also written to stdout
        assert rc == 0
        assert "advisory_id" in out_capture

    def test_table_prints_components(self, tmp_path: Path, capsys):
        audit = _write_audit_log(tmp_path / "cpp.jsonl", [
            _obs(cef_type="external_obstacle", severity="medium",
                 band="none", marker_count=3),
        ])
        rc = main(["--audit-log", str(audit), "--table"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "pay" in out
        assert "exploitability" in out


# ---------------------------------------------------------------------------
# TestSubprocess
# ---------------------------------------------------------------------------


class TestSubprocess:
    def test_subprocess_clean(self, tmp_path: Path):
        audit = _write_audit_log(tmp_path / "cpp.jsonl", [_obs()])
        result = subprocess.run(
            [sys.executable, "-m", "cli.aibom_review",
             "--audit-log", str(audit), "--summary"],
            capture_output=True, text=True,
            cwd="/home/workspace/agi-research",
        )
        assert result.returncode == 0
        assert "AIBOM Advisory" in result.stdout

    def test_subprocess_cef(self, tmp_path: Path):
        audit = _write_audit_log(tmp_path / "cpp.jsonl", [
            _obs(cef_type="external_obstacle", severity="high", band="high",
                 marker_count=3, level_index=5),
        ])
        result = subprocess.run(
            [sys.executable, "-m", "cli.aibom_review",
             "--audit-log", str(audit), "--summary"],
            capture_output=True, text=True,
            cwd="/home/workspace/agi-research",
        )
        assert result.returncode == 1  # HIGH -> REMEDIATE
        assert "remediate" in result.stdout

    def test_subprocess_thanatosis(self, tmp_path: Path):
        audit = _write_audit_log(tmp_path / "cpp.jsonl", [
            _obs(cef_type="simulated_crash", severity="critical", band="critical",
                 marker_count=4, level_index=7),
        ])
        result = subprocess.run(
            [sys.executable, "-m", "cli.aibom_review",
             "--audit-log", str(audit), "--summary"],
            capture_output=True, text=True,
            cwd="/home/workspace/agi-research",
        )
        assert result.returncode == 2  # BLOCK
        assert "thanatosis_count" in result.stdout

    def test_subprocess_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "cli.aibom_review", "--help"],
            capture_output=True, text=True,
            cwd="/home/workspace/agi-research",
        )
        assert result.returncode == 0
        assert "AIBOM" in result.stdout
        assert "--audit-log" in result.stdout
