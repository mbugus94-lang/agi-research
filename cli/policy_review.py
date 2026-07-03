"""CLI for reviewing VerbPolicyBundle audit logs.

Usage:
    python -m cli.policy_review <bundle.py:build> [--last N] [--by-source]

Or:
    python -m cli.policy_review --jsonl path/to/audit.jsonl

Builds on the 2026-07-03 VerbPolicyBundle work (arXiv:2606.19390,
AIBOM/CSAF-VEX "structured runtime telemetry" + "deterministic
replay" pattern).
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional


def review_bundle(bundle: Any, last: Optional[int] = None) -> Dict[str, Any]:
    """Review a VerbPolicyBundle's audit log.

    Returns a summary dict with counts by source, last N events,
    and the head hash for tamper detection.
    """
    log = bundle.audit_log()
    events = log.events() if hasattr(log, "events") else []
    if last is not None:
        events = events[-last:]
    counts: Dict[str, int] = Counter(e.source.value for e in events)
    return {
        "bundle_id": getattr(bundle, "library_id", ""),
        "n_entries": len(events),
        "counts_by_source": dict(counts),
        "last_events": [e.to_dict() for e in events[-5:]],
        "head_hash": log.last_hash() if hasattr(log, "last_hash") else None,
        "chain_valid": log.verify_chain() if hasattr(log, "verify_chain") else None,
    }


def review_jsonl(path: str, last: Optional[int] = None) -> Dict[str, Any]:
    """Review a JSONL audit log file."""
    p = Path(path)
    if not p.exists():
        return {"error": f"file not found: {path}"}
    events: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    if last is not None:
        events = events[-last:]
    counts: Dict[str, int] = Counter(
        e.get("source", "unknown") for e in events
    )
    return {
        "file": path,
        "n_entries": len(events),
        "counts_by_source": dict(counts),
        "last_events": events[-5:],
    }


def print_summary(summary: Dict[str, Any], out: Any = None) -> None:
    """Print a human-readable summary."""
    out = out or sys.stdout
    print("=" * 60, file=out)
    if "bundle_id" in summary:
        print(f"Bundle: {summary['bundle_id']}", file=out)
    elif "file" in summary:
        print(f"File:   {summary['file']}", file=out)
    print(f"Entries: {summary['n_entries']}", file=out)
    if summary.get("counts_by_source"):
        print("By source:", file=out)
        for src, n in sorted(summary["counts_by_source"].items()):
            print(f"  {src}: {n}", file=out)
    if summary.get("chain_valid") is not None:
        print(f"Chain valid: {summary['chain_valid']}", file=out)
    if summary.get("head_hash"):
        print(f"Head hash: {summary['head_hash'][:16]}...", file=out)
    if summary.get("last_events"):
        print("\nLast events:", file=out)
        for e in summary["last_events"]:
            verb = e.get("verb_name", "?")
            version = e.get("verb_version", "?")
            source = e.get("source", "?")
            kind = e.get("event_kind", e.get("kind", "?"))
            print(f"  [{kind}] {verb}@{version} -> {source}", file=out)
    print("=" * 60, file=out)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Review VerbPolicyBundle audit log")
    parser.add_argument("--jsonl", help="Path to a JSONL audit log file")
    parser.add_argument("--last", type=int, default=None, help="Show only the last N events")
    parser.add_argument(
        "--module",
        help="Python module:function that returns a VerbPolicyBundle",
    )
    args = parser.parse_args(argv)
    if args.jsonl:
        summary = review_jsonl(args.jsonl, last=args.last)
    elif args.module:
        mod_name, _, fn_name = args.module.partition(":")
        import importlib
        mod = importlib.import_module(mod_name)
        bundle = getattr(mod, fn_name)()
        summary = review_bundle(bundle, last=args.last)
    else:
        parser.error("either --jsonl or --module is required")
    print_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
