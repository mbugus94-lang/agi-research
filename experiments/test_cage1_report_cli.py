"""Tests for the opt-in CAGE-1 report comparison mode."""

from __future__ import annotations

import json
import subprocess
import sys


def _snapshot(label: str, digest: str, admitted: int, refused: int, score: float) -> dict:
    return {
        "label": label,
        "report_digest": digest,
        "n_reports": admitted + refused,
        "outcome_distribution": {
            "admitted": admitted,
            "held_for_evidence": 0,
            "narrowed_for_ring": 0,
            "narrowed_for_chain": 0,
            "quarantined_for_cef": 0,
            "escalated": 0,
            "refused": refused,
            "made_non_effective": 0,
        },
        "dimensions": [
            {"dimension": "authority_and_policy_enforcement", "coverage": "measured", "score": score},
            {"dimension": "retrieval_quality", "coverage": "not_measured", "score": None},
        ],
    }


def test_report_cli_comparison_json_mode(tmp_path):
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    before.write_text(json.dumps(_snapshot("before", "a", 3, 0, 0.5)), encoding="utf-8")
    after.write_text(json.dumps(_snapshot("after", "b", 2, 1, 0.8)), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cli.cage1_report",
            "--compare-snapshot",
            str(before),
            "--compare-snapshot",
            str(after),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert len(payload["trend"]["points"]) == 2
    assert len(payload["comparisons"]) == 1
    assert payload["comparisons"][0]["digest_match"] is False


def test_report_cli_comparison_markdown_mode(tmp_path):
    paths = []
    for index in range(3):
        path = tmp_path / f"snapshot-{index}.json"
        path.write_text(json.dumps(_snapshot(str(index), str(index), 3 - index, index, 0.5 + index * 0.1)), encoding="utf-8")
        paths.append(path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cli.cage1_report",
            *sum((["--compare-snapshot", str(path)] for path in paths), []),
            "--format",
            "markdown",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "CAGE-1 Trend" in result.stdout
    assert "Adjacent comparisons" in result.stdout


def test_report_cli_comparison_requires_two_snapshots():
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_report", "--compare-snapshot", "one.json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "at least two paths" in result.stderr


def test_report_cli_default_mode_remains_available():
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_report", "--demo", "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["label"] == "default"


def test_report_cli_fleet_input_jsonl_mode(tmp_path):
    path = tmp_path / "fleet.jsonl"
    rows = [
        {
            "label": "session-1",
            "report_digest": "one",
            "n_reports": 1,
            "substrate_coverage": 0.5,
            "outcome_distribution": {"admitted": 1, "refused": 0, "total": 1},
            "dimensions": [],
            "memory_integrity": {"measured": False},
            "retrieval_quality": {"measured": False},
        },
        {
            "label": "session-2",
            "report_digest": "two",
            "n_reports": 2,
            "substrate_coverage": 0.75,
            "outcome_distribution": {"admitted": 1, "refused": 1, "total": 2},
            "dimensions": [],
            "memory_integrity": {"measured": True, "score": 0.8},
            "retrieval_quality": {"measured": False},
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_report", "--fleet-input", str(path), "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert [item["label"] for item in payload["sessions"]] == ["session-1", "session-2"]
    assert payload["outcome_totals"]["admitted"] == 2


def test_report_cli_fleet_input_is_read_only(tmp_path):
    path = tmp_path / "fleet.json"
    row = {"label": "session-1", "report_digest": "one", "n_reports": 1, "outcome_distribution": {"admitted": 1}, "dimensions": []}
    original = json.dumps([row])
    path.write_text(original, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_report", "--fleet-input", str(path), "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert path.read_text(encoding="utf-8") == original


def test_report_cli_fleet_malformed_jsonl_reports_line(tmp_path):
    path = tmp_path / "malformed-fleet.jsonl"
    path.write_text(
        json.dumps({"label": "session-1", "report_digest": "one", "n_reports": 1, "outcome_distribution": {"admitted": 1}})
        + "\nnot-json\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_report", "--fleet-input", str(path), "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "line 2" in result.stderr


def test_report_cli_fleet_preserves_duplicate_and_decreasing_anomalies(tmp_path):
    path = tmp_path / "anomalous-fleet.json"
    rows = [
        {"label": "session-2", "report_digest": "same", "n_reports": 1, "outcome_distribution": {"admitted": 1}},
        {"label": "session-1", "report_digest": "same", "n_reports": 1, "outcome_distribution": {"admitted": 1}},
    ]
    path.write_text(json.dumps(rows), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_report", "--fleet-input", str(path), "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    anomalies = json.loads(result.stdout)["anomalies"]
    assert any("label order decreases" in item for item in anomalies)
    assert any("duplicate digest" in item for item in anomalies)


def test_report_cli_fleet_preserves_mixed_coverage(tmp_path):
    path = tmp_path / "mixed-fleet.json"
    rows = [
        {"label": "session-1", "report_digest": "one", "n_reports": 1, "outcome_distribution": {"admitted": 1}, "memory_integrity": {"measured": False}},
        {"label": "session-2", "report_digest": "two", "n_reports": 1, "outcome_distribution": {"admitted": 1}, "memory_integrity": {"measured": True, "score": 0.8}},
    ]
    path.write_text(json.dumps(rows), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_report", "--fleet-input", str(path), "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["sessions"][0]["memory_integrity"]["measured"] is False
    assert any(item["section"] == "memory_integrity" and item["metric"] == "score" and item["measured_sessions"] == 1 for item in payload["evidence_metrics"])


def test_report_cli_fleet_marks_nonfinite_optional_metrics_invalid(tmp_path):
    path = tmp_path / "nonfinite-fleet.json"
    row = {
        "label": "session-1",
        "report_digest": "one",
        "n_reports": 1,
        "outcome_distribution": {"admitted": 1},
        "memory_integrity": {"measured": True, "score": float("nan")},
        "retrieval_quality": {"measured": True, "recovery_score": float("inf")},
    }
    path.write_text(json.dumps([row], allow_nan=True), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_report", "--fleet-input", str(path), "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    invalid = payload["sessions"][0]["invalid_fields"]
    assert "memory_integrity.score" in invalid
    assert "retrieval_quality.recovery_score" in invalid
    assert payload["evidence_metrics"] == []


def _fleet_row(label: str, digest: str, *, measured: bool, score=0.8) -> dict:
    return {
        "label": label,
        "report_digest": digest,
        "n_reports": 1,
        "substrate_coverage": 0.5,
        "outcome_distribution": {"admitted": 1},
        "dimensions": [],
        "memory_integrity": {"measured": measured, "score": score} if measured else {"measured": False},
        "retrieval_quality": {"measured": False},
    }


def test_report_cli_fleet_malformed_jsonl_reports_source_line(tmp_path):
    path = tmp_path / "malformed-fleet.jsonl"
    path.write_text(json.dumps(_fleet_row("session-1", "one", measured=False)) + "\nnot-json\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_report", "--fleet-input", str(path), "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "line 2" in result.stderr


def test_report_cli_fleet_duplicate_digest_is_visible(tmp_path):
    path = tmp_path / "duplicate-fleet.json"
    path.write_text(json.dumps([
        _fleet_row("session-1", "same", measured=False),
        _fleet_row("session-2", "same", measured=False),
    ]), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_report", "--fleet-input", str(path), "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert any("duplicate digest" in item for item in json.loads(result.stdout)["anomalies"])


def test_report_cli_fleet_decreasing_labels_are_visible(tmp_path):
    path = tmp_path / "decreasing-fleet.json"
    path.write_text(json.dumps([
        _fleet_row("session-2", "one", measured=False),
        _fleet_row("session-1", "two", measured=False),
    ]), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_report", "--fleet-input", str(path), "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert any("label order decreases" in item for item in json.loads(result.stdout)["anomalies"])


def test_report_cli_fleet_mixed_evidence_keeps_coverage_explicit(tmp_path):
    path = tmp_path / "mixed-fleet.json"
    path.write_text(json.dumps([
        _fleet_row("session-1", "one", measured=False),
        _fleet_row("session-2", "two", measured=True, score=0.9),
    ]), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_report", "--fleet-input", str(path), "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["sessions"][0]["memory_integrity"]["measured"] is False
    assert any(item["metric"] == "score" and item["measured_sessions"] == 1 for item in payload["evidence_metrics"])


def test_report_cli_fleet_nonfinite_metrics_are_invalid_not_scores(tmp_path):
    path = tmp_path / "nonfinite-fleet.json"
    row = _fleet_row("session-1", "one", measured=True, score=float("nan"))
    path.write_text(json.dumps([row], allow_nan=True), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_report", "--fleet-input", str(path), "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "memory_integrity.score" in payload["sessions"][0]["invalid_fields"]
    assert payload["evidence_metrics"] == []
