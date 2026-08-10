"""Validation for read-only ordered per-verb CAGE-1 fleet aggregation."""

from __future__ import annotations

import json
import subprocess
import sys

from core.cage1_verb_fleet import aggregate_verb_comparisons, aggregate_verb_comparison_files, load_comparison
from core.cage1_verb_compare import compare_verb_profiles


def profile(label, digest, rows):
    return {"label": label, "report_digest": digest, "profiles": rows}


def row(verb, n, admitted, non_admitted, refused, escalated, worst):
    return {"verb_name": verb, "n_observations": n, "admitted_rate": admitted, "non_admitted_rate": non_admitted, "refusal_rate": refused, "escalation_rate": escalated, "worst_state": worst}


def comparison(baseline_label, current_label, rows):
    return compare_verb_profiles(profile(baseline_label, baseline_label + "-digest", rows), profile(current_label, current_label + "-digest", rows))


def test_empty_fleet_is_unverified_and_has_no_action():
    result = aggregate_verb_comparisons([])
    assert result.status == "unverified"
    assert result.snapshot_count == 0
    assert result.profiles == ()
    assert result.decision_applied is False
    assert result.automatic_action_taken is False


def test_aggregate_preserves_order_and_union_of_verbs(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(json.dumps(compare_verb_profiles(profile("a", "a", [row("read", 2, 1.0, 0.0, 0.0, 0.0, "admitted")]), profile("b", "b", [row("read", 2, 1.0, 0.0, 0.0, 0.0, "admitted"), row("old", 1, 0.0, 1.0, 1.0, 0.0, "refused")] )).to_dict()), encoding="utf-8")
    second.write_text(json.dumps(compare_verb_profiles(profile("b", "b", [row("read", 2, 1.0, 0.0, 0.0, 0.0, "admitted"), row("old", 1, 0.0, 1.0, 1.0, 0.0, "refused")]), profile("c", "c", [row("read", 4, 0.5, 0.5, 0.25, 0.0, "refused"), row("new", 1, 1.0, 0.0, 0.0, 0.0, "admitted")] )).to_dict()), encoding="utf-8")
    result = aggregate_verb_comparison_files([str(first), str(second)], snapshot_ids=["s1", "s2"])
    assert result.snapshot_ids == ("s1", "s2")
    assert [item.verb_name for item in result.profiles] == ["new", "old", "read"]
    assert result.profiles[0].coverage_changed is True
    assert result.profiles[1].removed_count == 1
    assert result.profiles[2].snapshot_count == 2
    assert result.profiles[2].latest_worst_state == "refused"
    assert result.automatic_action_taken is False


def test_missing_metrics_are_retained_as_coverage_not_zero():
    before = profile("a", "a", [row("write", 1, None, None, None, None, "")])
    after = profile("b", "b", [row("write", 2, 0.5, 0.5, 0.5, 0.0, "refused")])
    result = aggregate_verb_comparisons([
        load_comparison_from_values("snap", compare_verb_profiles(before, after).to_dict())
    ])
    item = result.profiles[0]
    assert item.statuses == {"coverage_changed": 1}
    assert item.coverage_changed is True
    assert item.observation_delta == 1


def load_comparison_from_values(snapshot_id, value):
    from core.cage1_verb_fleet import VerbComparisonSnapshot
    return VerbComparisonSnapshot(snapshot_id, "<memory>", "baseline", "current", "a", "b", value["changed_profile_count"], len(value["profiles"]), tuple(value["profiles"]))


def test_cli_json_and_markdown_are_read_only(tmp_path):
    baseline = profile("a", "a", [row("read", 1, 1.0, 0.0, 0.0, 0.0, "admitted")])
    current = profile("b", "b", [row("read", 2, 0.5, 0.5, 0.5, 0.0, "refused")])
    source = tmp_path / "comparison.json"
    source.write_text(json.dumps(compare_verb_profiles(baseline, current).to_dict()), encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "cli.cage1_verb_fleet", "--comparison", str(source), "--snapshot-id", "run-1", "--format", "json"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["snapshot_ids"] == ["run-1"]
    assert payload["profiles"][0]["verb_name"] == "read"
    assert payload["automatic_action_taken"] is False


def test_cli_rejects_mismatched_snapshot_ids(tmp_path):
    source = tmp_path / "comparison.json"
    source.write_text(json.dumps(compare_verb_profiles(profile("a", "a", []), profile("b", "b", [])).to_dict()), encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "cli.cage1_verb_fleet", "--comparison", str(source), "--comparison", str(source), "--snapshot-id", "only-one", "--format", "json"], capture_output=True, text=True)
    assert result.returncode == 2
    assert "once per --comparison" in result.stderr
