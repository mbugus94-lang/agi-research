#!/usr/bin/env python3
"""Render a read-only fleet aggregation over ordered CAGE-1 snapshots."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from core.cage1_fleet import aggregate_fleet, load_fleet_snapshots


def _fixture_snapshots(name: str) -> list[dict]:
    base = {
        "n_reports": 2,
        "substrate_coverage": 0.75,
        "outcome_distribution": {"admitted": 2, "refused": 0, "total": 2},
        "dimensions": [{"dimension": "authority", "coverage": "measured", "score": 0.75}],
    }
    if name == "mixed-coverage":
        return [
            {
                **base,
                "label": "session-1",
                "report_digest": "fixture-mixed-1",
                "memory_integrity": {"measured": False},
                "retrieval_quality": {"measured": False},
            },
            {
                **base,
                "label": "session-2",
                "report_digest": "fixture-mixed-2",
                "memory_integrity": {"measured": True, "score": 0.9, "record_count": 4},
                "retrieval_quality": {"measured": True, "score": 0.8, "recovery_score": 0.7},
            },
        ]
    return [
        {**base, "label": "session-1", "report_digest": "fixture-duplicate"},
        {**base, "label": "session-2", "report_digest": "fixture-duplicate"},
    ]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cli.cage1_fleet",
        description="Aggregate CAGE-1 session snapshots without applying policy changes.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", help="JSON array or JSONL file of ordered CAGE-1 evaluation snapshots.")
    source.add_argument("--fixture", choices=("mixed-coverage", "duplicate-digest"), help="Run a deterministic read-only fixture without an input file.")
    parser.add_argument("--format", choices=("markdown", "json", "both"), default="both", help="Output format; both writes Markdown to stdout and JSON to stderr.")
    parser.add_argument("--notes", default="", help="Optional report note.")
    args = parser.parse_args(argv)
    try:
        snapshots = _fixture_snapshots(args.fixture) if args.fixture else load_fleet_snapshots(args.input)
        note = args.notes or (f"fixture: {args.fixture}" if args.fixture else "")
        fleet = aggregate_fleet(snapshots, notes=note)
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
