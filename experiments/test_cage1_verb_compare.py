"""Validation for read-only per-verb CAGE-1 profile comparison."""

from __future__ import annotations

import json
import subprocess
import sys

from core.cage1_verb_compare import compare_verb_profiles


def profile(label, digest, rows):
    return {"label": label, "report_digest": digest, "profiles": rows}


def row(verb, n, admitted, non_admitted, refused, escalated, worst):
    return {
        "verb_name": verb,
        "n_observations": n,
        "admitted_rate": admitted,
        "non_admitted_rate": non_admitted,
        "refusal_rate": refused,
        "escalation_rate": escalated,
        "worst_state": worst,
    }


def test_comparison_aligns_union_and_preserves_added_removed_verbs():
    result = compare_verb_profiles(
        profile("baseline", "a", [row("read", 2, 1.0, 0.0, 0.0, 0.0, "admitted"), row("old", 1, 0.0, 1.0, 1.0, 0.0, "refused")]),
        profile("current", "b", [row("read", 4, 0.5, 0.5, 0.25, 0.0, "refused"), row("new", 1, 1.0, 0.0, 0.0, 0.0, "admitted")]),
    )
    assert [item.verb_name for item in result.profiles] == ["new", "old", "read"]
    assert result.profiles[0].status == "added"
    assert result.profiles[1].status == "removed"
    assert result.profiles[2].admitted_rate_delta == -0.5
    assert result.profiles[2].refusal_rate_delta == 0.25
    assert result.changed_profile_count == 3


def test_same_profile_is_unchanged_and_digest_match_is_explicit():
    snapshot = profile("same", "digest", [row("search", 3, 1.0, 0.0, 0.0, 0.0, "admitted")])
    result = compare_verb_profiles(snapshot, snapshot)
    assert result.digest_match is True
    assert result.changed_profile_count == 0
    assert result.profiles[0].status == "unchanged"
    assert result.profiles[0].observation_delta == 0


def test_missing_rates_are_coverage_changed_not_zero():
    result = compare_verb_profiles(
        profile("a", "a", [row("write", 1, None, None, None, None, "")]),
        profile("b", "b", [row("write", 1, 0.0, 1.0, 1.0, 0.0, "refused")]),
    )
    item = result.profiles[0]
    assert item.status == "coverage_changed"
    assert item.admitted_rate_delta is None
    assert item.current_admitted_rate == 0.0


def test_serialization_markdown_and_cli_json(tmp_path):
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    baseline.write_text(json.dumps(profile("a", "a", [row("read", 1, 1.0, 0.0, 0.0, 0.0, "admitted")])), encoding="utf-8")
    current.write_text(json.dumps(profile("b", "b", [row("read", 2, 0.5, 0.5, 0.5, 0.0, "refused")])), encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "cli.cage1_verb_compare", "--baseline", str(baseline), "--current", str(current), "--format", "json"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["profiles"][0]["verb_name"] == "read"
    assert "Per-verb CAGE-1 Comparison" in compare_verb_profiles(json.loads(baseline.read_text()), json.loads(current.read_text())).to_markdown()


def test_invalid_cli_input_is_fail_closed(tmp_path):
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    baseline.write_text("[]", encoding="utf-8")
    current.write_text("{}", encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "cli.cage1_verb_compare", "--baseline", str(baseline), "--current", str(current), "--format", "json"], capture_output=True, text=True)
    assert result.returncode == 2
    assert "profile JSON must contain an object" in result.stderr
