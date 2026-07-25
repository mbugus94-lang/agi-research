"""Compare CAGE-1 fleet audit summaries without applying decisions."""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from core.cage1_decision_fleet_trend import trend_fleet_audit_files, write_fleet_audit_trend_jsonl


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="cli.cage1_fleet_trend", description="Trend CAGE-1 fleet audit summaries without applying decisions.")
    parser.add_argument("--summary", action="append", required=True, help="Fleet audit summary JSON; repeat in chronological order.")
    parser.add_argument("--snapshot-id", action="append", help="Optional snapshot identity; repeat once per --summary.")
    parser.add_argument("--out", help="Write the trend document as JSON.")
    parser.add_argument("--audit-out", help="Write points, deltas, and summary as JSONL.")
    parser.add_argument("--summary-only", action="store_true", help="Print compact trend status.")
    args = parser.parse_args(argv)
    try:
        trend = trend_fleet_audit_files(args.summary, snapshot_ids=args.snapshot_id)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(trend.to_json() + "\n")
        if args.audit_out:
            write_fleet_audit_trend_jsonl(trend, args.audit_out)
        if args.summary_only:
            print(f"status={trend.status} points={len(trend.points)} deltas={len(trend.deltas)} flags={len(trend.flagged_changes)}")
        else:
            print(trend.to_json())
        return 0 if trend.status in {"stable", "improving"} else 1
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
