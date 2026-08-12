from __future__ import annotations

import json
import subprocess
import sys

from core.cage1_verb_evidence_join import join_verb_fleet_evidence


def fleet(*profiles, status="valid"):
    return {
        "category": "cage1_verb_comparison_fleet",
        "schema_version": "1.0",
        "status": status,
        "snapshot_ids": ["run-1", "run-2"],
        "profiles": list(profiles),
        "decision_applied": False,
        "automatic_action_taken": False,
    }


def profile(name, state="admitted", coverage=False, delta=0):
    return {
        "verb_name": name,
        "latest_status": "changed" if state != "admitted" else "unchanged",
        "latest_worst_state": state,
        "coverage_changed": coverage,
        "observation_delta": delta,
    }


def evidence(*rows):
    return {
        "category": "cage1_decision_fleet_audit",
        "schema_version": "1.0",
        "lines": list(rows),
    }


def row(status="valid", decision="defer", verb_name=None, source_id="member.jsonl", line=3, operator="op-1"):
    value = {
        "status": status,
        "decision": decision,
        "operator_id": operator,
        "source_id": source_id,
        "source_line_number": line,
        "advisory_digest": "adv-1",
    }
    if verb_name is not None:
        value["verb_name"] = verb_name
    return value


def test_missing_evidence_is_unverified_and_review_only():
    result = join_verb_fleet_evidence(fleet(profile("read")))
    assert result.status == "unverified"
    assert result.evidence_status == "missing"
    assert result.profiles[0].join_status == "no_evidence"
    assert result.decision_applied is False
    assert result.automatic_action_taken is False


def test_join_matches_explicit_verb_and_preserves_provenance():
    result = join_verb_fleet_evidence(
        fleet(profile("read"), profile("write", state="refused", coverage=True, delta=2)),
        evidence(row(verb_name="read"), row(verb_name="write", decision="reject", source_id="member-b.jsonl", line=8, operator="op-2")),
    )
    assert result.status == "matched"
    assert result.evidence_status == "present"
    assert [item.verb_name for item in result.profiles] == ["read", "write"]
    assert result.profiles[0].join_status == "matched"
    assert result.profiles[1].decision_counts == {"reject": 1}
    assert result.profiles[1].operator_ids == ("op-2",)
    assert result.evidence_rows[1].source_line_number == 8
    assert result.snapshot_ids == ("run-1", "run-2")


def test_unmatched_and_unattributed_evidence_are_not_dropped():
    result = join_verb_fleet_evidence(
        fleet(profile("read")),
        evidence(row(verb_name="read"), row(verb_name="ghost"), row()),
    )
    assert result.status == "partial"
    assert result.unmatched_identity_count == 1
    assert result.unattributed_evidence_count == 1
    assert [item.verb_name for item in result.profiles] == ["__unattributed__", "ghost", "read"]
    assert result.profiles[0].join_status == "unmatched_evidence"
    assert result.profiles[1].join_status == "unmatched_evidence"
    assert result.profiles[2].join_status == "matched"


def test_invalid_evidence_status_is_counted_and_does_not_count_as_valid():
    result = join_verb_fleet_evidence(
        fleet(profile("read")),
        evidence(row(status="invalid_schema", decision=None, verb_name="read")),
    )
    assert result.status == "matched"
    assert result.profiles[0].valid_evidence_count == 0
    assert result.profiles[0].evidence_status_counts == {"invalid_schema": 1}
    assert result.decision_counts == {}


def test_cli_json_and_markdown_are_read_only(tmp_path):
    fleet_path = tmp_path / "fleet.json"
    evidence_path = tmp_path / "evidence.json"
    out_path = tmp_path / "joined.json"
    fleet_path.write_text(json.dumps(fleet(profile("read"))), encoding="utf-8")
    evidence_path.write_text(json.dumps(evidence(row(verb_name="read"))), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_verb_evidence_join", "--fleet", str(fleet_path), "--evidence", str(evidence_path), "--out", str(out_path), "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "matched"
    assert payload["profiles"][0]["verb_name"] == "read"
    assert payload["automatic_action_taken"] is False
    assert json.loads(out_path.read_text(encoding="utf-8"))["decision_applied"] is False
    assert json.loads(fleet_path.read_text(encoding="utf-8"))["profiles"][0]["verb_name"] == "read"


def test_json_markdown_parity_preserves_sorted_profiles_and_provenance():
    result = join_verb_fleet_evidence(
        fleet(profile("write", state="refused", coverage=True, delta=2), profile("read")),
        evidence(
            row(verb_name="write", decision="reject", source_id="write.jsonl", line=8, operator="op-2"),
            row(verb_name="read", source_id="read.jsonl", line=4),
        ),
    )
    payload = json.loads(result.to_json())
    markdown = result.to_markdown()
    assert [item["verb_name"] for item in payload["profiles"]] == ["read", "write"]
    assert payload["evidence_status_counts"] == {"valid": 2}
    assert payload["decision_counts"] == {"defer": 1, "reject": 1}
    assert markdown.index("| `read` |") < markdown.index("| `write` |")
    assert "source=`read.jsonl`, line=4" in markdown
    assert "source=`write.jsonl`, line=8" in markdown
    assert "Decision applied: **no**" in markdown
    assert payload["automatic_action_taken"] is False


def test_identity_fallback_is_consistent_across_json_and_markdown():
    result = join_verb_fleet_evidence(
        fleet(profile("read"), profile("write"), profile("sync")),
        evidence(
            row(verb_name="read"),
            {"status": "valid", "action_type": "write", "decision": "accept", "source_id": "action.jsonl", "line_number": 6},
            {"status": "invalid_schema", "detail": {"tool": "sync"}, "source_id": "tool.jsonl", "source_line_number": 9},
        ),
    )
    payload = json.loads(result.to_json())
    markdown = result.to_markdown()
    assert [item["verb_name"] for item in payload["profiles"]] == ["read", "sync", "write"]
    assert [item["verb_name"] for item in payload["evidence_rows"]] == ["read", "write", "sync"]
    assert "`valid`: verb=`write`, source=`action.jsonl`, line=6" in markdown
    assert "`invalid_schema`: verb=`sync`, source=`tool.jsonl`, line=9" in markdown
    assert payload["profiles"][1]["valid_evidence_count"] == 0
    assert payload["profiles"][1]["evidence_status_counts"] == {"invalid_schema": 1}


def test_adversarial_mixed_status_preserves_invalid_provenance_and_never_invents_validity():
    result = join_verb_fleet_evidence(
        fleet(profile("read"), profile("sync")),
        evidence(
            row(verb_name="read", source_id="valid.jsonl", line=4),
            {
                "status": "invalid_schema",
                "detail": {"tool": "read"},
                "source_id": "invalid.jsonl",
                "source_line_number": True,
                "decision": "accept",
            },
            {
                "status": "unknown_status",
                "action_type": "sync",
                "source_id": "unknown.jsonl",
                "line_number": -2,
                "operator_id": "op-2",
            },
        ),
    )
    payload = json.loads(result.to_json())
    markdown = result.to_markdown()
    read_profile = next(item for item in payload["profiles"] if item["verb_name"] == "read")
    sync_profile = next(item for item in payload["profiles"] if item["verb_name"] == "sync")
    assert result.status == "matched"
    assert payload["evidence_status_counts"] == {"invalid_schema": 1, "unknown_status": 1, "valid": 1}
    assert read_profile["evidence_status_counts"] == {"invalid_schema": 1, "valid": 1}
    assert read_profile["valid_evidence_count"] == 1
    assert read_profile["decision_counts"] == {"defer": 1}
    assert read_profile["evidence_rows"][1]["source_line_number"] is None
    assert sync_profile["evidence_status_counts"] == {"unknown_status": 1}
    assert sync_profile["valid_evidence_count"] == 0
    assert sync_profile["evidence_rows"][0]["source_line_number"] == -2
    assert "`invalid_schema`: verb=`read`, source=`invalid.jsonl`, line=unknown" in markdown
    assert "`unknown_status`: verb=`sync`, source=`unknown.jsonl`, line=-2" in markdown
    assert payload["decision_applied"] is False
    assert payload["automatic_action_taken"] is False
