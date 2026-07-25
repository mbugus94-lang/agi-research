"""Aggregate verification-only CAGE-1 decision audit JSONL files."""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from core.cage1_decision_fleet import aggregate_decision_audit_files, write_fleet_audit_jsonl


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cli.cage1_fleet_audit",
        description="Aggregate CAGE-1 decision audit JSONL files without applying decisions.",
    )
    parser.add_argument("--audit", action="append", required=True, help="Decision audit JSONL path; repeat for each fleet member.")
    parser.add_argument("--report", action="append", help="Optional consumer report JSON; repeat once per --audit.")
    parser.add_argument("--out", help="Write the fleet summary as JSON.")
    parser.add_argument("--audit-out", help="Write flattened fleet lines plus a final summary as JSONL.")
    parser.add_argument("--summary", action="store_true", help="Print compact counts instead of the full JSON document.")
    args = parser.parse_args(argv)
    try:
        summary = aggregate_decision_audit_files(args.audit, report_paths=args.report)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(summary.to_json() + "\n")
        if args.audit_out:
            write_fleet_audit_jsonl(summary, args.audit_out)
        if args.summary:
            print(
                f"status={summary.status} sources={summary.source_count} "
                f"lines={summary.line_count} valid={summary.valid_line_count} "
                f"invalid={summary.invalid_line_count} "
                f"advisories={len(summary.advisory_counts)}"
            )
        else:
            print(summary.to_json())
        return 0 if summary.status == "valid" else 1
    except (OSError, ValueError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
