"""
CONTRA-style benign-config finder CLI.

Operator-facing search primitive: given a *known dangerous chain* (the
JADEPUFFER attack, or any other pattern in the CAGE-1 control set), search
the policy space for *benign-looking* mutations that admit the chain. The
hits are reviewed (never auto-applied) by a security engineer.

This is the substrate's analog of the CONTRA paper's "benign config finder":
a tree-search that probes the policy space for paths that "look" innocuous
(low drop in classification, minimal cluster reshuffling) but produce
dangerous chains under a different verb naming or relaxed taint budget.

Usage:
    python -m cli.contra_search \\
        --policies policies.json \\
        --chain chain.json \\
        [--max-depth 3] [--max-results 8] [--time-budget-ms 2000] \\
        [--summary] [--json]

Exit codes:
    0 = search completed; hits printed (may be zero)
    1 = search completed; at least one HIGH-severity hit
    2 = invalid input

Policy JSON format: same as cli.dscc_clearance (extended VerbPolicy).
Chain JSON format: same as cli.dscc_clearance.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Sequence

from core.benign_config_finder import (
    BenignConfigFinder,
    SearchBudget,
    derive_search_space,
    jadepuffer_target_chain,
)
from core.compositional_policy import (
    ChainStep,
    ClassificationLevel,
    CompositionMode,
    TaintSource,
    VerbPolicy,
    create_gate,
)


def _parse_classification(value: Any) -> ClassificationLevel:
    if isinstance(value, ClassificationLevel):
        return value
    return ClassificationLevel.parse(value)


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
        classification=_parse_classification(d.get("classification", "public")),
        cluster=str(d.get("cluster", "default")),
    )


def _parse_step(d: Dict[str, Any]) -> ChainStep:
    return ChainStep(
        verb_name=d["verb_name"],
        taint_in=TaintSource(d.get("taint_in", "internal")),
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="contra_search",
        description="CONTRA-style benign-config finder (operator review tool)",
    )
    parser.add_argument(
        "--policies", required=True, help="JSON file of verb policies"
    )
    parser.add_argument(
        "--chain",
        default=None,
        help="JSON file describing the target chain (default: JADEPUFFER)",
    )
    parser.add_argument(
        "--max-depth", type=int, default=3, help="Max mutation depth (default 3)"
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=8,
        help="Max hits to emit (default 8). 0 = unlimited.",
    )
    parser.add_argument(
        "--time-budget-ms",
        type=int,
        default=2000,
        help="Wall-clock budget in ms (default 2000)",
    )
    parser.add_argument(
        "--mode",
        choices=("clearance", "taint"),
        default="clearance",
        help="Composition mode for the shadow gate (default clearance)",
    )
    parser.add_argument(
        "--summary", action="store_true", help="One-line summary per hit"
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_out", help="Emit JSON only"
    )

    args = parser.parse_args(argv)

    try:
        with open(args.policies, "r", encoding="utf-8") as f:
            policies_doc = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: could not read --policies file: {e}", file=sys.stderr)
        return 2
    if not isinstance(policies_doc, dict):
        print("ERROR: --policies must be a JSON object", file=sys.stderr)
        return 2

    policies: Dict[str, VerbPolicy] = {}
    for name, p in policies_doc.items():
        if not isinstance(p, dict):
            print(f"ERROR: policy[{name}] is not an object", file=sys.stderr)
            return 2
        try:
            policies[name] = _parse_policy(p)
        except (KeyError, ValueError) as e:
            print(f"ERROR: policy[{name}]: {e}", file=sys.stderr)
            return 2

    if args.chain is not None:
        try:
            with open(args.chain, "r", encoding="utf-8") as f:
                chain_doc = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"ERROR: could not read --chain file: {e}", file=sys.stderr)
            return 2
        if not isinstance(chain_doc, dict) or "steps" not in chain_doc:
            print("ERROR: --chain must be a JSON object with 'steps' key", file=sys.stderr)
            return 2
        try:
            target_chain: Sequence[ChainStep] = [_parse_step(s) for s in chain_doc["steps"]]
        except (KeyError, ValueError) as e:
            print(f"ERROR: chain step: {e}", file=sys.stderr)
            return 2
    else:
        target_chain = jadepuffer_target_chain()

    mode = CompositionMode.CLEARANCE if args.mode == "clearance" else CompositionMode.TAINT

    gate = create_gate(policies=policies, composition_mode=mode)

    space = derive_search_space(gate)
    if not space:
        if not args.json_out:
            print("No mutations available (empty policy registry or all immutable).")
        return 0

    budget = SearchBudget(
        max_depth=args.max_depth,
        time_budget_ms=args.time_budget_ms,
        max_iterations=0,
    )
    finder = BenignConfigFinder(
        target_chain=list(target_chain),
        gate=gate,
        composition_mode=mode,
        budget=budget,
        max_results=args.max_results,
    )
    hits = finder.search()

    if args.json_out:
        out = {
            "target_chain": [
                {"verb_name": s.verb_name, "taint_in": s.taint_in.value}
                for s in target_chain
            ],
            "composition_mode": mode.value,
            "search_space_size": len(space),
            "iterations": 0,  # tracked as local var in search(),
            "hits": [h.to_dict() for h in hits],
        }
        print(json.dumps(out, indent=2))
    elif args.summary:
        for h in hits:
            print(
                f"  {h.hit_type:<20s}  benign_score={h.benign_looking_score:.3f}  "
                f"mutations={len(h.mutations):2d}  digest={h.mutation_digest}"
            )
    else:
        print(f"Target chain ({len(target_chain)} steps):")
        for s in target_chain:
            print(f"  {s.verb_name}  (taint_in={s.taint_in.value})")
        print()
        print(f"Composition mode: {mode.value}")
        print(f"Search space size: {len(space)} mutations")
        print(f"Iterations: {0}")
        print(f"Hits: {len(hits)}")
        print()
        for i, h in enumerate(hits, 1):
            print(f"  Hit {i}:")
            print(f"    type:           {h.hit_type}")
            print(f"    benign_score:   {h.benign_looking_score:.3f}")
            print(f"    mutations:      {len(h.mutations)}")
            print(f"    digest:         {h.mutation_digest}")
            if h.mutations:
                for m in h.mutations:
                    print(f"      - {m.describe()}")
            print()

    has_high_severity = any(
        h.hit_type in ("adversarial_success", "missed_trip") for h in hits
    )
    return 1 if has_high_severity else 0


if __name__ == "__main__":
    raise SystemExit(main())
