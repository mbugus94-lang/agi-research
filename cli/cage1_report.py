#!/usr/bin/env python3
"""
CAGE-1 evaluation report CLI (arXiv:2607.03510, 2026-07).

Operator-facing entry point for the CAGE-1 evaluation module. Reads
a JSONL audit log of `CrossCheckReport` rows (each row is a dict
with at least an `outcome` or `cage1_state` field) and emits a
CAGE-1-shaped evaluation:

  - per-state distribution (admitted, held, narrowed, refused, etc.)
  - per-dimension scores (the 7 substrate-covered CAGE-1 dimensions)
  - operational readiness (trip_upper_bound mean/max, breaker opens)
  - a SHA-256 report digest for audit replay

Two modes:

  --audit-log <path>    : read report rows from a JSONL file
  --demo                : run a synthetic session (8 actions) and
                          evaluate the resulting reports
  --demo --include-breach : force a post-breach attempt in the demo

The output is always written to stdout. --format json emits the
machine-readable envelope; --format markdown emits an operator-
facing Markdown summary; the default is the markdown summary plus
the JSON envelope on stderr.

Exit code: 0 on success, 1 on parse/IO error, 2 on bad args.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from core.cage1_compare import compare_evaluations, load_evaluation
from core.cage1_evaluation import (
    CAGE1Evaluation,
    build_synthetic_session,
    evaluate_reports,
    load_reports_from_jsonl,
    cage1_state_distribution,
)
from core.cage1_trend import trend_evaluations


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="cli.cage1_report",
        description="CAGE-1 evaluation report CLI (arXiv:2607.03510).",
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument(
        "--audit-log",
        metavar="PATH",
        help="JSONL audit log of report rows (one JSON object per line).",
    )
    src.add_argument(
        "--demo",
        action="store_true",
        help="Run a synthetic session and evaluate the reports.",
    )
    src.add_argument(
        "--compare-snapshot",
        action="append",
        metavar="PATH",
        help="Compare two or more saved CAGE-1 JSON snapshots; repeat for each path.",
    )
    p.add_argument(
        "--demo-actions",
        type=int,
        default=8,
        help="Number of actions in the synthetic session (default 8).",
    )
    p.add_argument(
        "--demo-seed",
        type=int,
        default=0,
        help="Seed for the synthetic session (default 0).",
    )
    p.add_argument(
        "--include-breach",
        action="store_true",
        help="(demo) include a post-breach attempt in the synthetic session.",
    )
    p.add_argument(
        "--label",
        default="default",
        help="Evaluation label (default 'default').",
    )
    p.add_argument(
        "--format",
        choices=["markdown", "json", "both"],
        default="both",
        help="Output format (default both = markdown on stdout, json on stderr).",
    )
    p.add_argument(
        "--notes",
        default="",
        help="Optional notes to attach to the evaluation.",
    )
    p.add_argument(
        "--exit-on-escalation",
        action="store_true",
        help="Exit with code 1 if any action was escalated (held for human).",
    )
    p.add_argument(
        "--exit-on-refusal",
        action="store_true",
        help="Exit with code 1 if any action was refused.",
    )
    return p.parse_args(argv)


def _load_reports(
    args: argparse.Namespace,
) -> tuple[list, str]:
    """Load report rows from the chosen source.

    Returns (rows, source_label) where `rows` is a list of
    CrossCheckReport / dict and source_label is a human-readable
    description of where they came from.
    """
    if args.demo:
        loop, reports = build_synthetic_session(
            n_actions=args.demo_actions,
            seed=args.demo_seed,
            include_breach=args.include_breach,
        )
        return reports, f"demo: {args.demo_actions} actions, seed={args.demo_seed}"
    if args.audit_log:
        rows = load_reports_from_jsonl(args.audit_log)
        return rows, f"audit-log: {args.audit_log} ({len(rows)} rows)"
    return [], "(no source)"


def _emit(
    evaluation: CAGE1Evaluation,
    fmt: str,
) -> None:
    if fmt == "json":
        print(evaluation.to_json())
    elif fmt == "markdown":
        print(evaluation.to_cage1_markdown())
    else:  # both
        print(evaluation.to_cage1_markdown())
        print("---", file=sys.stderr)
        print(evaluation.to_json(), file=sys.stderr)


def _comparison_payload(snapshot_paths: List[str], notes: str) -> tuple[dict, str]:
    snapshots = [load_evaluation(path) for path in snapshot_paths]
    trend = trend_evaluations(snapshots, notes=notes)
    comparisons = [
        compare_evaluations(snapshots[index - 1], snapshots[index], notes=notes)
        for index in range(1, len(snapshots))
    ]
    payload = {
        "trend": trend.to_dict(),
        "comparisons": [comparison.to_dict() for comparison in comparisons],
    }
    markdown = trend.to_markdown()
    if comparisons:
        markdown += "\n## Adjacent comparisons\n\n"
        markdown += "\n".join(comparison.to_markdown().rstrip() for comparison in comparisons)
        markdown += "\n"
    return payload, markdown


def _emit_comparison(payload: dict, markdown: str, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif fmt == "markdown":
        print(markdown)
    else:
        print(markdown)
        print("---", file=sys.stderr)
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    if args.compare_snapshot is not None:
        if len(args.compare_snapshot) < 2:
            print("ERROR: --compare-snapshot requires at least two paths", file=sys.stderr)
            return 2
        try:
            payload, markdown = _comparison_payload(args.compare_snapshot, args.notes)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        _emit_comparison(payload, markdown, args.format)
        return 0

    if not args.demo and not args.audit_log:
        print(
            "ERROR: must supply --audit-log PATH or --demo",
            file=sys.stderr,
        )
        return 2

    try:
        reports, source = _load_reports(args)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"ERROR: malformed JSONL: {exc}", file=sys.stderr)
        return 1

    if not reports:
        print("ERROR: no reports to evaluate", file=sys.stderr)
        return 1

    evaluation = evaluate_reports(
        reports,
        label=args.label,
        notes=(args.notes or f"source: {source}"),
    )
    _emit(evaluation, args.format)

    if args.exit_on_escalation and evaluation.outcome_distribution.escalated:
        return 1
    if args.exit_on_refusal and evaluation.outcome_distribution.refused:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
