"""CLI for emitting AIBOM (AI Bill of Materials) advisories.

Builds on core/aibom_advisory.py (arXiv:2606.19390). Reads a CPP
JSONL audit log + an optional bundle snapshot and emits a self-
contained AIBOMAdvisory JSON document. The advisory is the operator-
facing handoff from the constraint-pressure probe (skills/cpp.py) to
the agent gateway control plane (Forbes, Jul 5 2026) and to a human
reviewer (MedSkillAudit-style pre-deployment gate).

Usage:
    python -m cli.aibom_review --audit-log cpp.jsonl --out advisory.json
    python -m cli.aibom_review --audit-log cpp.jsonl --bundle-snapshot bundle.json \\
        --out advisory.json --status final
    python -m cli.aibom_review --audit-log cpp.jsonl --summary
    cat advisory.json | jq .severity,.recommendation,.advisory_id

Conservative posture:
  - The CLI does not auto-act on the advisory. The advisory is written
    to a JSON file and a human-readable summary is printed to stdout.
  - The CLI never modifies the audit log or the bundle snapshot; both
    are read-only inputs.
  - Exit codes: 0 = advisory emitted (clean or otherwise), 1 = any
    HIGH+ severity, 2 = any CRITICAL+thanatosis (CET / BLOCK).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from core.aibom_advisory import (
    AdvisoryAction,
    AdvisoryCategory,
    AdvisorySeverity,
    AdvisoryStatus,
    AIBOMAdvisory,
    emit_aibom_advisory,
    load_audit_log,
    try_emit_from_bundle,
    write_advisory,
)


def _load_bundle_snapshot(path: Optional[str]) -> Optional[Dict[str, Any]]:
    """Load a bundle snapshot from JSON. Returns None if no path or file missing."""
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _format_summary(advisory: AIBOMAdvisory) -> str:
    """Human-readable summary of the advisory."""
    lines = [
        f"AIBOM Advisory: {advisory.advisory_id[:16]}...",
        f"  category:     {advisory.category}",
        f"  severity:     {advisory.severity}",
        f"  recommendation: {advisory.recommendation}",
        f"  status:       {advisory.status}",
        f"  worst_band:   {advisory.worst_band}",
        f"  total_observations: {advisory.total_observations}",
        f"  thanatosis_count:   {advisory.thanatosis_count}",
        f"  component_count:    {advisory.component_count}",
        f"  bundle_library_id:  {advisory.bundle_library_id}",
        f"  audit_log_path:     {advisory.audit_log_path}",
        f"  evidence_digest:    {advisory.evidence_digest[:16] or '(empty)'}...",
        f"  cef_substrate:      {advisory.cef_substrate_available}",
        f"  generated_at:       {advisory.generated_at:.3f}",
    ]
    if advisory.vulnerabilities:
        lines.append("  findings:")
        for v in advisory.vulnerabilities[:10]:
            cid = v.get("component_id", "?")
            sev = v.get("severity", "?")
            band = v.get("observed_band", "?")
            lines.append(f"    - {cid}  severity={sev}  band={band}")
        if len(advisory.vulnerabilities) > 10:
            lines.append(f"    ... and {len(advisory.vulnerabilities) - 10} more")
    return "\n".join(lines)


def _format_advisory_table(advisory: AIBOMAdvisory) -> str:
    """Per-component table for the summary view."""
    lines = ["component                       band    severity  exploitability  recommendation"]
    lines.append("-" * 86)
    for c in advisory.product_tree.get("components", []):
        cid = c.get("component_id", "?")[:30]
        band = c.get("observed_band", "?")
        sev = c.get("observed_severity", "?")
        expl = c.get("exploitability", "?")
        rec = c.get("recommendation", "?")
        lines.append(f"  {cid:<30}  {band:<6}  {sev:<8}  {expl:<13}  {rec}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cli.aibom_review",
        description=(
            "Emit an AIBOM advisory from a CPP JSONL audit log "
            "(+ optional bundle snapshot). The advisory is the "
            "arXiv:2606.19390 handoff from probe audit to human "
            "reviewer / agent gateway control plane."
        ),
    )
    parser.add_argument(
        "--audit-log",
        required=True,
        help="Path to the CPP JSONL audit log (one record per line).",
    )
    parser.add_argument(
        "--bundle-snapshot",
        default=None,
        help=(
            "Path to a JSON-serialized bundle snapshot "
            "(library_id + default_config + entries). Optional."
        ),
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Path to write the AIBOMAdvisory JSON. If omitted, "
        "the advisory is emitted to stdout.",
    )
    parser.add_argument(
        "--status",
        default=AdvisoryStatus.INTERIM.value,
        choices=[s.value for s in AdvisoryStatus],
        help="Advisory status (default: interim).",
    )
    parser.add_argument(
        "--title",
        default="AGI substrate AIBOM advisory",
        help="Document title.",
    )
    parser.add_argument(
        "--publisher",
        default="agi-research",
        help="Document publisher name.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print the human-readable summary to stdout.",
    )
    parser.add_argument(
        "--table",
        action="store_true",
        help="Print a per-component table to stdout.",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Do not print anything to stdout. Just write the advisory.",
    )
    args = parser.parse_args(argv)

    # Load inputs
    audit_log_path = args.audit_log
    audit_log_records = load_audit_log(audit_log_path)
    bundle_snapshot = _load_bundle_snapshot(args.bundle_snapshot)

    # Emit the advisory
    advisory = emit_aibom_advisory(
        observations=audit_log_records,
        bundle_snapshot=bundle_snapshot,
        audit_log_path=audit_log_path,
        audit_log_records=audit_log_records,
        title=args.title,
        publisher=args.publisher,
        status=args.status,
    )

    # Write to disk
    if args.out:
        write_advisory(advisory, args.out)

    # Stdout output: JSON goes to stdout only if --out is absent OR if
    # neither --summary nor --table was requested (i.e., the operator
    # wants the raw JSON). --summary and --table are mutually
    # exclusive with raw-JSON-on-stdout: if either is requested, the
    # operator wants the formatted view.
    if not args.silent:
        wants_formatted = bool(args.summary or args.table)
        if args.out and not wants_formatted:
            # File written; also dump JSON to stdout (operator's
            # default "show me the document" path)
            print(json.dumps(advisory.to_dict(), indent=2, sort_keys=True))
        elif not args.out and not wants_formatted:
            # No --out: write JSON to stdout
            print(json.dumps(advisory.to_dict(), indent=2, sort_keys=True))
        # else: --out + --summary/--table: only formatted view
        #       --summary/--table alone: only formatted view
        if args.summary:
            print(_format_summary(advisory))
        if args.table:
            print(_format_advisory_table(advisory))

    # Exit code: 0 = clean/defer/monitor, 1 = HIGH+ (remediate), 2 = CRITICAL+thanatosis (BLOCK)
    if advisory.recommendation == AdvisoryAction.BLOCK.value:
        return 2
    if advisory.recommendation == AdvisoryAction.REMEDIATE.value:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
