"""
CLI: Compositional Policy Review (arXiv:2607.03423 DSCC-style).

Operator-facing entry point for the compositional policy gate. Reads a
JSON policy file describing (verb_name -> VerbPolicy) and a JSON chain
file describing the proposed tool chain, then prints the verdict.

Usage:
    python -m cli.compositional_review \\
        --policies policies.json \\
        --chain chain.json \\
        --summary

Exit codes:
    0 = ALLOW
    1 = ALLOW_ONLY_REVIEW
    2 = BLOCK
    3 = BLOCK_AND_ESCALATE

Policy JSON format (each VerbPolicy is a dict):
    {
      "read_env": {
        "verb_name": "read_env",
        "taint_in": "internal",
        "sinks": ["read"],
        "requires_review": false,
        "max_taint_threshold": null,
        "is_secret_emitting": false,
        "is_secret_accepting": false
      }
    }

Chain JSON format:
    {
      "steps": [
        {"verb_name": "read_env", "taint_in": "internal"},
        {"verb_name": "http_post_external", "taint_in": "external"}
      ]
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

from core.compositional_policy import (
    ChainAction,
    ChainStep,
    CompositionalPolicyGate,
    TaintSource,
    VerbPolicy,
    create_gate,
)


_EXIT_CODES = {
    ChainAction.ALLOW: 0,
    ChainAction.ALLOW_ONLY_REVIEW: 1,
    ChainAction.BLOCK: 2,
    ChainAction.BLOCK_AND_ESCALATE: 3,
}


def _parse_policy(d: Dict[str, Any]) -> VerbPolicy:
    taint_in = TaintSource(d.get("taint_in", "internal"))
    return VerbPolicy(
        verb_name=d["verb_name"],
        taint_in=taint_in,
        sinks=tuple(d.get("sinks", ())),
        requires_review=bool(d.get("requires_review", False)),
        max_taint_threshold=(
            TaintSource(d["max_taint_threshold"])
            if d.get("max_taint_threshold")
            else None
        ),
        is_secret_emitting=bool(d.get("is_secret_emitting", False)),
        is_secret_accepting=bool(d.get("is_secret_accepting", False)),
    )


def _parse_step(d: Dict[str, Any]) -> ChainStep:
    return ChainStep(
        verb_name=d["verb_name"],
        taint_in=TaintSource(d.get("taint_in", "internal")),
    )


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="compositional_review",
        description="Compositional policy gate review CLI",
    )
    parser.add_argument("--policies", required=True, help="JSON file of verb policies")
    parser.add_argument("--chain", required=True, help="JSON file describing the proposed chain")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print human-readable summary to stderr",
    )
    parser.add_argument(
        "--max-sinks",
        type=int,
        default=CompositionalPolicyGate.DEFAULT_MAX_SINKS,
        help="Maximum distinct sinks before fanout alarm (default: 3)",
    )
    args = parser.parse_args(argv)

    try:
        with open(args.policies, "r", encoding="utf-8") as fh:
            policies_raw = json.load(fh)
        with open(args.chain, "r", encoding="utf-8") as fh:
            chain_raw = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: failed to load input: {e}", file=sys.stderr)
        return 3

    policies = {name: _parse_policy(p) for name, p in policies_raw.items()}
    steps = [_parse_step(s) for s in chain_raw.get("steps", [])]

    gate = create_gate(policies=policies, max_sinks=args.max_sinks)
    verdict = gate.check_chain(steps)

    print(json.dumps(verdict.to_dict(), indent=2))
    if args.summary:
        print(
            f"\nverdict: {verdict.action.value} | "
            f"reasons: {[r.value for r in verdict.reasons]} | "
            f"digest: {verdict.digest[:16]}...",
            file=sys.stderr,
        )

    return _EXIT_CODES[verdict.action]


if __name__ == "__main__":
    sys.exit(main())
