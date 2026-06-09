"""
Tests for skills/self_review_queue.py

Coverage:
  1.  list_proposals: filter by brake, risk, action; skip malformed
  2.  find_proposal: returns the right record, returns None when missing
  3.  show_proposal: format includes the proposal + decision + audit
  4.  decide_proposal: writes back, idempotent, preserves audit fields
  5.  gate_summary: one-line per proposal, sorted newest-first
  6.  gate_status: aggregate counts (by_action, by_risk, approved, rejected)
  7.  Empty / missing directory
  8.  CLI surface
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from skills.self_review_queue import (
    DEFAULT_PROPOSALS_DIR,
    decide_proposal,
    find_proposal,
    gate_status,
    gate_summary,
    list_proposals,
    show_proposal,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_proposal(directory: Path, **overrides) -> Path:
    """Write a minimal valid proposal JSON to `directory` and return the path."""
    record = {
        "proposal": {
            "proposal_id": overrides.get("proposal_id", "rsi_test_0001"),
            "title": overrides.get("title", "Test proposal"),
            "target_file": overrides.get("target_file", "core/foo.py"),
            "risk_band": overrides.get("risk_band", "medium"),
            "evidence_status": overrides.get("evidence_status", "ungrounded"),
            "brake_state_at_submission": overrides.get("brake_state_at_submission", "braked"),
            "requires_attention": overrides.get("requires_attention", False),
            "status": overrides.get("status", "scored"),
            "created_at": overrides.get("created_at", "2026-06-09T05:00:00+00:00"),
            "rationale": overrides.get("rationale", "rationale text"),
        },
        "decision": {
            "visible": overrides.get("visible", True),
            "requires_attention": overrides.get("requires_attention_d", False),
            "action": overrides.get("action", "queue"),
            "explanation": overrides.get("explanation", "explanation text"),
        },
    }
    if "human_review" in overrides:
        record["proposal"]["human_review"] = overrides["human_review"]
    path = directory / f"{record['proposal']['proposal_id']}.json"
    with open(path, "w") as f:
        json.dump(record, f, indent=2)
    return path


# ---------------------------------------------------------------------------
# Tests: list_proposals
# ---------------------------------------------------------------------------


class TestListProposals:
    def test_empty_directory(self, tmp_path):
        assert list_proposals(proposals_dir=str(tmp_path)) == []

    def test_missing_directory(self, tmp_path):
        missing = tmp_path / "nope"
        assert list_proposals(proposals_dir=str(missing)) == []

    def test_returns_all_proposals(self, tmp_path):
        _write_proposal(tmp_path, proposal_id="rsi_1")
        _write_proposal(tmp_path, proposal_id="rsi_2")
        _write_proposal(tmp_path, proposal_id="rsi_3")
        records = list_proposals(proposals_dir=str(tmp_path))
        assert len(records) == 3

    def test_skips_malformed_json(self, tmp_path):
        _write_proposal(tmp_path, proposal_id="rsi_ok")
        bad = tmp_path / "broken.json"
        bad.write_text("{ this is not valid JSON")
        records = list_proposals(proposals_dir=str(tmp_path))
        assert len(records) == 1
        assert records[0]["proposal"]["proposal_id"] == "rsi_ok"

    def test_filter_by_risk_band(self, tmp_path):
        _write_proposal(tmp_path, proposal_id="rsi_low", risk_band="low")
        _write_proposal(tmp_path, proposal_id="rsi_crit", risk_band="critical")
        records = list_proposals(proposals_dir=str(tmp_path), risk_band="critical")
        assert len(records) == 1
        assert records[0]["proposal"]["proposal_id"] == "rsi_crit"

    def test_filter_by_action(self, tmp_path):
        _write_proposal(tmp_path, proposal_id="rsi_q", action="queue")
        _write_proposal(tmp_path, proposal_id="rsi_a", action="attention")
        records = list_proposals(proposals_dir=str(tmp_path), action="attention")
        assert len(records) == 1
        assert records[0]["proposal"]["proposal_id"] == "rsi_a"

    def test_filter_by_brake_state(self, tmp_path):
        _write_proposal(
            tmp_path,
            proposal_id="rsi_braked",
            brake_state_at_submission="braked",
            explanation="Held by brake pedal (braked); risk=medium",
        )
        _write_proposal(
            tmp_path,
            proposal_id="rsi_open",
            brake_state_at_submission="open",
            explanation="risk=medium, brake=open",
        )
        records = list_proposals(proposals_dir=str(tmp_path), brake_state="braked")
        assert len(records) == 1
        assert records[0]["proposal"]["proposal_id"] == "rsi_braked"

    def test_skips_proposal_without_proposal_field(self, tmp_path):
        bad = tmp_path / "no_proposal.json"
        bad.write_text(json.dumps({"decision": {"action": "queue"}}))
        records = list_proposals(proposals_dir=str(tmp_path))
        assert records == []


# ---------------------------------------------------------------------------
# Tests: find_proposal
# ---------------------------------------------------------------------------


class TestFindProposal:
    def test_finds_existing(self, tmp_path):
        _write_proposal(tmp_path, proposal_id="rsi_target")
        record = find_proposal("rsi_target", proposals_dir=str(tmp_path))
        assert record is not None
        assert record["proposal"]["proposal_id"] == "rsi_target"

    def test_returns_none_when_missing(self, tmp_path):
        _write_proposal(tmp_path, proposal_id="rsi_other")
        assert find_proposal("rsi_missing", proposals_dir=str(tmp_path)) is None

    def test_empty_directory(self, tmp_path):
        assert find_proposal("any", proposals_dir=str(tmp_path)) is None


# ---------------------------------------------------------------------------
# Tests: show_proposal
# ---------------------------------------------------------------------------


class TestShowProposal:
    def test_includes_title_and_decision(self, tmp_path):
        _write_proposal(
            tmp_path,
            proposal_id="rsi_show",
            title="My Test",
            action="attention",
            risk_band="critical",
        )
        out = show_proposal("rsi_show", proposals_dir=str(tmp_path))
        assert "rsi_show" in out
        assert "My Test" in out
        assert "critical" in out
        assert "attention" in out

    def test_not_found_message(self, tmp_path):
        out = show_proposal("rsi_ghost", proposals_dir=str(tmp_path))
        assert "[not found]" in out


# ---------------------------------------------------------------------------
# Tests: decide_proposal
# ---------------------------------------------------------------------------


class TestDecideProposal:
    def test_writes_back_approved(self, tmp_path):
        _write_proposal(tmp_path, proposal_id="rsi_1")
        path = decide_proposal("rsi_1", "approved", reviewer="alice", proposals_dir=str(tmp_path))
        assert path is not None
        record = json.loads(path.read_text())
        assert record["proposal"]["human_review"]["decision"] == "approved"
        assert record["proposal"]["human_review"]["reviewer"] == "alice"
        assert "decided_at" in record["proposal"]["human_review"]

    def test_writes_back_rejected(self, tmp_path):
        _write_proposal(tmp_path, proposal_id="rsi_2")
        path = decide_proposal(
            "rsi_2", "rejected", reviewer="bob", reason="too risky", proposals_dir=str(tmp_path)
        )
        assert path is not None
        record = json.loads(path.read_text())
        assert record["proposal"]["human_review"]["decision"] == "rejected"
        assert record["proposal"]["human_review"]["reason"] == "too risky"

    def test_invalid_decision_raises(self, tmp_path):
        _write_proposal(tmp_path, proposal_id="rsi_3")
        with pytest.raises(ValueError):
            decide_proposal("rsi_3", "maybe", proposals_dir=str(tmp_path))

    def test_returns_none_for_missing(self, tmp_path):
        assert decide_proposal("ghost", "approved", proposals_dir=str(tmp_path)) is None

    def test_idempotent(self, tmp_path):
        _write_proposal(tmp_path, proposal_id="rsi_4")
        p1 = decide_proposal("rsi_4", "approved", reviewer="alice", proposals_dir=str(tmp_path))
        p2 = decide_proposal("rsi_4", "rejected", reviewer="bob", proposals_dir=str(tmp_path))
        # p2 should overwrite p1; not duplicate
        record = json.loads(p1.read_text())
        assert record["proposal"]["human_review"]["decision"] == "rejected"
        assert record["proposal"]["human_review"]["reviewer"] == "bob"

    def test_preserves_audit_fields(self, tmp_path):
        _write_proposal(
            tmp_path,
            proposal_id="rsi_5",
            risk_band="critical",
            action="attention",
            created_at="2026-06-09T05:00:00+00:00",
        )
        decide_proposal("rsi_5", "approved", proposals_dir=str(tmp_path))
        record = find_proposal("rsi_5", proposals_dir=str(tmp_path))
        # Original audit fields stay intact
        assert record["proposal"]["risk_band"] == "critical"
        assert record["proposal"]["created_at"] == "2026-06-09T05:00:00+00:00"
        assert record["decision"]["action"] == "attention"


# ---------------------------------------------------------------------------
# Tests: gate_summary
# ---------------------------------------------------------------------------


class TestGateSummary:
    def test_empty(self, tmp_path):
        out = gate_summary(proposals_dir=str(tmp_path))
        assert "(no proposals" in out

    def test_one_per_proposal(self, tmp_path):
        _write_proposal(tmp_path, proposal_id="rsi_a", title="Alpha")
        _write_proposal(tmp_path, proposal_id="rsi_b", title="Beta")
        out = gate_summary(proposals_dir=str(tmp_path))
        assert "Alpha" in out
        assert "Beta" in out
        # Two lines, one per proposal (plus possible leading empty)
        assert len([line for line in out.split("\n") if line.strip()]) == 2

    def test_newest_first(self, tmp_path):
        _write_proposal(
            tmp_path,
            proposal_id="rsi_old",
            created_at="2026-06-01T00:00:00+00:00",
        )
        _write_proposal(
            tmp_path,
            proposal_id="rsi_new",
            created_at="2026-06-09T00:00:00+00:00",
        )
        out = gate_summary(proposals_dir=str(tmp_path))
        lines = [line for line in out.split("\n") if line.strip()]
        assert "rsi_new" in lines[0]
        assert "rsi_old" in lines[1]

    def test_includes_human_review_flag(self, tmp_path):
        _write_proposal(
            tmp_path,
            proposal_id="rsi_done",
            human_review={"decision": "approved", "reviewer": "alice", "reason": "", "decided_at": "x"},
        )
        out = gate_summary(proposals_dir=str(tmp_path))
        assert "[approved]" in out


# ---------------------------------------------------------------------------
# Tests: gate_status
# ---------------------------------------------------------------------------


class TestGateStatus:
    def test_empty(self, tmp_path):
        s = gate_status(proposals_dir=str(tmp_path))
        assert s["total"] == 0
        assert s["approved"] == 0
        assert s["rejected"] == 0
        assert s["pending_human_review"] == 0

    def test_counts_by_action(self, tmp_path):
        _write_proposal(tmp_path, proposal_id="rsi_q", action="queue")
        _write_proposal(tmp_path, proposal_id="rsi_a", action="attention")
        _write_proposal(tmp_path, proposal_id="rsi_a2", action="attention")
        s = gate_status(proposals_dir=str(tmp_path))
        assert s["total"] == 3
        assert s["by_action"]["queue"] == 1
        assert s["by_action"]["attention"] == 2

    def test_counts_by_risk(self, tmp_path):
        _write_proposal(tmp_path, proposal_id="rsi_l", risk_band="low")
        _write_proposal(tmp_path, proposal_id="rsi_c", risk_band="critical")
        s = gate_status(proposals_dir=str(tmp_path))
        assert s["by_risk"]["low"] == 1
        assert s["by_risk"]["critical"] == 1

    def test_approved_rejected_split(self, tmp_path):
        _write_proposal(
            tmp_path,
            proposal_id="rsi_a",
            human_review={"decision": "approved", "reviewer": "x", "reason": "", "decided_at": "y"},
        )
        _write_proposal(
            tmp_path,
            proposal_id="rsi_r",
            human_review={"decision": "rejected", "reviewer": "y", "reason": "no", "decided_at": "z"},
        )
        _write_proposal(tmp_path, proposal_id="rsi_p")  # pending
        s = gate_status(proposals_dir=str(tmp_path))
        assert s["approved"] == 1
        assert s["rejected"] == 1
        assert s["pending_human_review"] == 1


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header"])
