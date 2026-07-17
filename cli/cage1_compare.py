#!/usr/bin/env python3
"""Compare two saved CAGE-1 evaluation JSON snapshots."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from core.cage1_compare import compare_evaluations, load_evaluation


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cli.cage1_compare",
        description="Compare two CAGE-1 evaluation JSON snapshots without applying policy changes.",
    )
    parser.add_argument("--baseline", required=True, help="Baseline evaluation JSON path.")
    parser.add_argument("--current", required=True, help="Current evaluation JSON path.")
    parser.add_argument("--format", choices=("markdown", "json", "both"), default="both")
    parser.add_argument("--notes", default="", help="Optional comparison note.")
    args = parser.parse_args(argv)
    try:
        comparison = compare_evaluations(
            load_evaluation(args.baseline),
            load_evaluation(args.current),
            notes=args.notes,
        )
    except (OSError, ValueError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.format in ("markdown", "both"):
        print(comparison.to_markdown())
    if args.format == "json":
        print(comparison.to_json())
    elif args.format == "both":
        print(comparison.to_json(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
