"""Aggregate ordered per-verb CAGE-1 comparisons without applying policy."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from core.cage1_verb_fleet import aggregate_verb_comparison_files


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m cli.cage1_verb_fleet", description="Aggregate per-verb CAGE-1 comparison snapshots in read-only mode.")
    parser.add_argument("--comparison", action="append", required=True, help="Comparison JSON path; repeat for each ordered snapshot.")
    parser.add_argument("--snapshot-id", action="append", help="Stable snapshot ID; repeat once per --comparison.")
    parser.add_argument("--format", choices=("markdown", "json", "both"), default="both")
    args = parser.parse_args(argv)
    try:
        summary = aggregate_verb_comparison_files(args.comparison, snapshot_ids=args.snapshot_id)
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.format in ("markdown", "both"):
        print(summary.to_markdown())
    if args.format == "json":
        print(summary.to_json())
    elif args.format == "both":
        print(summary.to_json(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
