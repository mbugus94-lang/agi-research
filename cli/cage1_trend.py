#!/usr/bin/env python3
"""Render a read-only trend report over ordered CAGE-1 snapshots."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from core.cage1_trend import load_evaluations, trend_evaluations


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cli.cage1_trend",
        description="Report CAGE-1 score trajectories, digest lineage, and regressions.",
    )
    parser.add_argument("--input", required=True, help="JSON array of ordered CAGE-1 evaluation snapshots.")
    parser.add_argument("--format", choices=("markdown", "json", "both"), default="both")
    parser.add_argument("--notes", default="", help="Optional report note.")
    args = parser.parse_args(argv)
    try:
        trend = trend_evaluations(load_evaluations(args.input), notes=args.notes)
    except (OSError, ValueError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.format in ("markdown", "both"):
        print(trend.to_markdown())
    if args.format == "json":
        print(trend.to_json())
    elif args.format == "both":
        print(trend.to_json(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
