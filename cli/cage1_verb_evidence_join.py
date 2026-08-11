"""Join per-verb fleet profiles with decision evidence in read-only mode."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from core.cage1_verb_evidence_join import join_verb_fleet_evidence, load_json


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cli.cage1_verb_evidence_join",
        description="Join per-verb CAGE-1 fleet profiles with explicit decision evidence without applying policy.",
    )
    parser.add_argument("--fleet", required=True, help="Per-verb fleet comparison JSON path.")
    parser.add_argument("--evidence", help="Decision fleet, trend envelope, or evidence JSON path.")
    parser.add_argument("--format", choices=("markdown", "json", "both"), default="both")
    parser.add_argument("--out", help="Write the JSON join summary to this path.")
    args = parser.parse_args(argv)
    try:
        fleet = load_json(args.fleet)
        evidence = load_json(args.evidence) if args.evidence else None
        summary = join_verb_fleet_evidence(fleet, evidence)
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(summary.to_json() + "\n")
    if args.format in ("markdown", "both"):
        print(summary.to_markdown())
    if args.format == "json":
        print(summary.to_json())
    elif args.format == "both":
        print(summary.to_json(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
