"""
Self-Review Queue - Operator interface for the proposals/ directory.

Implements the Jun 7 priority list's "human review terminal":
  - list_proposals():   filter proposals by brake state / risk band
  - show_proposal():    pretty-print a single proposal + decision
  - decide_proposal():  write approve/reject back to the JSON
  - gate_summary():     one-line per-proposal status for terminal view
  - gate_status():      aggregate counts

This module is intentionally thin: the RSI controller is the system
of record (it writes the JSON), and the queue is a read/write
operator surface on top of those files. No state is held in memory;
restarting the process loses nothing except the *in-memory* audit
trail, which the JSON files preserve.

The decide_proposal() function is the *only* path in the system
that should ever modify a file in the proposals/ directory outside
of the controller. SAFETY.md says self-modifications require human
review; this is the human's pen.

Substrate-respecting:
  - Reads/writes the same JSON shape that RSIController.persist() writes
  - Never touches the EvidenceLedger or the brake pedal directly
  - Audit fields stay immutable (timestamp, brake state, decision action)
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Default proposals directory (relative to repo root)
DEFAULT_PROPOSALS_DIR = "proposals"


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def list_proposals(
    proposals_dir: str = DEFAULT_PROPOSALS_DIR,
    brake_state: Optional[str] = None,
    risk_band: Optional[str] = None,
    action: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return every proposal JSON in proposals_dir, optionally filtered.

    Filters:
      brake_state - keep only proposals whose `decision.explanation`
                    mentions the given state (e.g. "braked")
      risk_band   - keep only proposals whose `proposal.risk_band`
                    matches (e.g. "critical")
      action      - keep only proposals whose `decision.action` matches
                    (e.g. "attention", "queue", "gate")

    Malformed JSON is skipped silently. A proposal without a
    `proposal` field is also skipped.
    """
    p = Path(proposals_dir)
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    for path in sorted(p.glob("*.json")):
        try:
            with open(path) as f:
                record = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        proposal = record.get("proposal")
        decision = record.get("decision", {})
        if not isinstance(proposal, dict):
            continue
        if brake_state is not None:
            explanation = decision.get("explanation", "")
            if brake_state not in explanation:
                continue
        if risk_band is not None:
            if proposal.get("risk_band") != risk_band:
                continue
        if action is not None:
            if decision.get("action") != action:
                continue
        record["_path"] = str(path)
        out.append(record)
    return out


def find_proposal(
    proposal_id: str,
    proposals_dir: str = DEFAULT_PROPOSALS_DIR,
) -> Optional[Dict[str, Any]]:
    """Return a single proposal matching the given id, or None."""
    for record in list_proposals(proposals_dir=proposals_dir):
        proposal = record.get("proposal", {})
        if proposal.get("proposal_id") == proposal_id:
            return record
    return None


# ---------------------------------------------------------------------------
# Pretty-print
# ---------------------------------------------------------------------------


def show_proposal(
    proposal_id: str,
    proposals_dir: str = DEFAULT_PROPOSALS_DIR,
) -> str:
    """Render a single proposal + decision as a human-readable string."""
    record = find_proposal(proposal_id, proposals_dir=proposals_dir)
    if record is None:
        return f"[not found] proposal_id={proposal_id}"
    proposal = record.get("proposal", {})
    decision = record.get("decision", {})
    lines: List[str] = []
    lines.append(f"=== {proposal.get('proposal_id', '?')} ===")
    lines.append(f"title:        {proposal.get('title', '')}")
    lines.append(f"target_file:  {proposal.get('target_file') or '(none)'}")
    lines.append(f"risk_band:    {proposal.get('risk_band', '?')}")
    lines.append(f"evidence:     {proposal.get('evidence_status', '?')}")
    lines.append(f"brake@submit: {proposal.get('brake_state_at_submission', '?')}")
    lines.append(f"requires_attn:{proposal.get('requires_attention', False)}")
    lines.append(f"status:       {proposal.get('status', '?')}")
    lines.append(f"created_at:   {proposal.get('created_at', '?')}")
    lines.append(f"rationale:    {proposal.get('rationale', '')[:200]}")
    lines.append("---")
    lines.append(f"decision.action:           {decision.get('action', '?')}")
    lines.append(f"decision.visible:          {decision.get('visible', '?')}")
    lines.append(f"decision.requires_attention: {decision.get('requires_attention', '?')}")
    lines.append(f"decision.explanation:      {decision.get('explanation', '')}")
    payload = proposal.get("payload")
    if payload:
        preview = payload if len(payload) <= 400 else payload[:400] + "..."
        lines.append("---")
        lines.append(f"payload preview: {preview}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Decide
# ---------------------------------------------------------------------------


def decide_proposal(
    proposal_id: str,
    decision: str,
    reviewer: str = "",
    reason: str = "",
    proposals_dir: str = DEFAULT_PROPOSALS_DIR,
) -> Optional[Path]:
    """Write a human decision (approved / rejected) back to the proposal JSON.

    This is the *only* path that should ever modify a file in
    proposals/ outside of the RSI controller. The original
    audit fields (timestamp, brake state, decision action) are
    preserved; the new fields are added under
    `human_review.{decision, reviewer, reason, decided_at}`.

    Returns the path of the modified file, or None if the
    proposal is not found.
    """
    if decision not in {"approved", "rejected"}:
        raise ValueError(f"decision must be 'approved' or 'rejected', got {decision!r}")
    record = find_proposal(proposal_id, proposals_dir=proposals_dir)
    if record is None:
        return None
    path = Path(record["_path"])
    proposal = record.get("proposal", {})
    proposal.setdefault("human_review", {})
    # idempotent: replace any prior decision
    proposal["human_review"] = {
        "decision": decision,
        "reviewer": reviewer or "unknown",
        "reason": reason,
        "decided_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with open(path, "w") as f:
        json.dump(record, f, indent=2, sort_keys=True)
    return path


# ---------------------------------------------------------------------------
# Summary / status
# ---------------------------------------------------------------------------


def gate_summary(proposals_dir: str = DEFAULT_PROPOSALS_DIR) -> str:
    """One-line per-proposal status, sorted by created_at (newest first)."""
    records = list_proposals(proposals_dir=proposals_dir)
    if not records:
        return f"(no proposals in {proposals_dir}/)"
    lines: List[str] = []
    # newest first
    records.sort(
        key=lambda r: r.get("proposal", {}).get("created_at", ""),
        reverse=True,
    )
    for record in records:
        proposal = record.get("proposal", {})
        decision = record.get("decision", {})
        pid = proposal.get("proposal_id", "?")
        risk = proposal.get("risk_band", "?")
        action = decision.get("action", "?")
        brake = proposal.get("brake_state_at_submission", "?")
        title = (proposal.get("title", "") or "")[:50]
        human = proposal.get("human_review", {}).get("decision")
        flag = f" [{human}]" if human else ""
        lines.append(
            f"{pid}  {risk:<8}  {action:<10}  brake={brake:<7}  {title}{flag}"
        )
    return "\n".join(lines)


def gate_status(proposals_dir: str = DEFAULT_PROPOSALS_DIR) -> Dict[str, Any]:
    """Aggregate counts: visible, gated, attention, approved, rejected, by_risk."""
    records = list_proposals(proposals_dir=proposals_dir)
    actions = Counter()
    risk_counts = Counter()
    approved = 0
    rejected = 0
    for record in records:
        decision = record.get("decision", {})
        proposal = record.get("proposal", {})
        actions[decision.get("action", "?")] += 1
        risk_counts[proposal.get("risk_band", "?")] += 1
        human = proposal.get("human_review", {}).get("decision")
        if human == "approved":
            approved += 1
        elif human == "rejected":
            rejected += 1
    return {
        "total": len(records),
        "by_action": dict(actions),
        "by_risk": dict(risk_counts),
        "approved": approved,
        "rejected": rejected,
        "pending_human_review": len(records) - approved - rejected,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _cli(argv: List[str]) -> int:
    """Tiny CLI: list, show, decide, summary, status.

    Designed to be subcommand-driven so the operator can do:
        python -m skills.self_review_queue list
        python -m skills.self_review_queue show rsi_2026-06-09T05-00-00Z
        python -m skills.self_review_queue decide rsi_2026-06-09T05-00-00Z approved
    """
    if not argv:
        print("usage: self_review_queue {list,show,decide,summary,status}", file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "list":
        risk = None
        action = None
        brake = None
        i = 0
        while i < len(rest):
            if rest[i] == "--risk":
                risk = rest[i + 1]
                i += 2
            elif rest[i] == "--action":
                action = rest[i + 1]
                i += 2
            elif rest[i] == "--brake":
                brake = rest[i + 1]
                i += 2
            else:
                i += 1
        for record in list_proposals(risk_band=risk, action=action, brake_state=brake):
            print(record.get("proposal", {}).get("proposal_id", "?"))
        return 0
    if cmd == "show":
        if not rest:
            print("usage: show <proposal_id>", file=sys.stderr)
            return 2
        print(show_proposal(rest[0]))
        return 0
    if cmd == "decide":
        if len(rest) < 2:
            print("usage: decide <proposal_id> {approved|rejected} [--reviewer NAME] [--reason TEXT]", file=sys.stderr)
            return 2
        proposal_id, verdict = rest[0], rest[1]
        reviewer = ""
        reason = ""
        i = 2
        while i < len(rest):
            if rest[i] == "--reviewer":
                reviewer = rest[i + 1]
                i += 2
            elif rest[i] == "--reason":
                reason = rest[i + 1]
                i += 2
            else:
                i += 1
        path = decide_proposal(proposal_id, verdict, reviewer=reviewer, reason=reason)
        if path is None:
            print(f"[not found] {proposal_id}", file=sys.stderr)
            return 1
        print(f"wrote {path}")
        return 0
    if cmd == "summary":
        print(gate_summary())
        return 0
    if cmd == "status":
        print(json.dumps(gate_status(), indent=2, sort_keys=True))
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))


__all__ = [
    "DEFAULT_PROPOSALS_DIR",
    "list_proposals",
    "find_proposal",
    "show_proposal",
    "decide_proposal",
    "gate_summary",
    "gate_status",
]
