#!/usr/bin/env python3
"""Render a read-only fleet aggregation over ordered CAGE-1 snapshots."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from core.cage1_fleet import aggregate_fleet, load_fleet_snapshots


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cli.cage1_fleet",
        description="Aggregate CAGE-1 session snapshots without applying policy changes.",
    )
    parser.add_argument("--input", required=True, help="JSON array of ordered CAGE-1 evaluation snapshots.")
    parser.add_argument("--format", choices=("markdown", "json", "both"), default="both")
    parser.add_argument("--notes", default="", help="Optional report note.")
    args = parser.parse_args(argv)
    try:
        fleet = aggregate_fleet(load_fleet_snapshots(args.input), notes=args.notes)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.format in ("markdown", "both"):
        print(fleet.to_markdown())
    if args.format == "json":
        print(fleet.to_json())
    elif args.format == "both":
        print(fleet.to_json(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
