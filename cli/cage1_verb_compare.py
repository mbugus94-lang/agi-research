#!/usr/bin/env python3
"""Compare saved per-verb CAGE-1 profile snapshots without applying policy."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from core.cage1_verb_compare import compare_verb_profiles, load_profile


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cli.cage1_verb_compare",
        description="Compare per-verb CAGE-1 profile JSON snapshots in read-only mode.",
    )
    parser.add_argument("--baseline", required=True, help="Baseline profile JSON path.")
    parser.add_argument("--current", required=True, help="Current profile JSON path.")
    parser.add_argument("--format", choices=("markdown", "json", "both"), default="both")
    parser.add_argument("--notes", default="", help="Optional comparison note.")
    args = parser.parse_args(argv)
    try:
        comparison = compare_verb_profiles(load_profile(args.baseline), load_profile(args.current), notes=args.notes)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
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
