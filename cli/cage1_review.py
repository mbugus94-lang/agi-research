"""CLI for review-only CAGE-1 fleet/trend advisory projections."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Optional

from core.cage1_advisory import project_review_advisory, write_review_advisory
from core.cage1_fleet import aggregate_fleet, load_fleet_snapshots
from core.cage1_trend import trend_fleet_snapshots


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cli.cage1_review", description="Emit a review-only CAGE-1 fleet advisory.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fleet-input", help="Ordered CAGE-1 snapshots as JSON array or JSONL.")
    source.add_argument("--compare-snapshot", action="append", help="Saved snapshot path; repeat at least twice.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--out", help="Write the advisory JSON to this path.")
    parser.add_argument("--notes", default="")
    return parser


def _load_source(args: argparse.Namespace) -> Any:
    if args.fleet_input:
        return aggregate_fleet(load_fleet_snapshots(args.fleet_input), notes=args.notes)
    paths = args.compare_snapshot or []
    if len(paths) < 2:
        raise ValueError("--compare-snapshot requires at least two paths")
    snapshots = [json.loads(open(path, encoding="utf-8").read()) for path in paths]
    return trend_fleet_snapshots(snapshots, notes=args.notes)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        advisory = project_review_advisory(_load_source(args), notes=args.notes)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.out:
        write_review_advisory(advisory, args.out)
    if args.format == "markdown":
        print(advisory.to_markdown())
    else:
        print(advisory.to_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
