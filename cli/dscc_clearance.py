"""
DSCC Clearance-Mode CLI (arXiv:2607.03423 §2.2 Step 3).

Operator-facing entry point for the DSCC static-composition phase. The
substrate's `CompositionalPolicyGate` runs the MRS (Most Restrictive
Set) algorithm in clearance mode by default; this CLI exposes the
classification-aware subset of that algorithm for batch audit jobs.

The clearance check answers: "given a chain of tools T1,...,Tn with
per-tool classification levels C1,...,Cn, is every tool cleared to
handle data at the chain's high-water-mark classification C_eff?"

In clearance mode (the DSCC default), an under-classified tool causes a
DENY before any tool executes. In taint mode, the clearance check is
skipped and classification is treated as a sticky taint property of the
data instead. The CLI defaults to clearance mode.

Usage:
    python -m cli.dscc_clearance \\
        --policies policies.json \\
        --chain chain.json \\
        [--mode clearance|taint] \\
        [--summary] [--json]

Exit codes:
    0 = chain passes the clearance check
    1 = chain fails the clearance check
    2 = invalid input

Policy JSON format (each VerbPolicy is a dict, extended with DSCC
classification + cluster fields):
    {
      "read_env": {
        "verb_name": "read_env",
        "taint_in": "internal",
        "classification": "internal",  # DSCC field
        "cluster": "default"           # DSCC field (optional)
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
    ClassificationLevel,
    CompositionMode,
    CompositionalPolicyGate,
    DenyReason,
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


def _parse_clusters(d: Dict[str, Any]) -> Dict[str, str]:
    """Map verb_name -> cluster name."""
    return {str(k): str(v) for k, v in d.items()}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dscc_clearance",
        description="DSCC clearance-mode review CLI (arXiv:2607.03423)",
    )
    parser.add_argument(
        "--policies", required=True, help="JSON file of verb policies"
    )
    parser.add_argument(
        "--chain", required=True, help="JSON file describing the proposed chain"
    )
    parser.add_argument(
        "--clusters",
        default=None,
        help="Optional JSON file mapping verb_name -> cluster name",
    )
    parser.add_argument(
        "--initial-classification",
        default="public",
        help="Initial classification for the chain (default: public)",
    )
    parser.add_argument(
        "--mode",
        default="clearance",
        choices=("clearance", "taint"),
        help="Composition mode (default: clearance)",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a one-line summary of the clearance decision",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit JSON instead of text"
    )
    args = parser.parse_args(argv)

    try:
        with open(args.policies) as f:
            raw_policies = json.load(f)
    except (OSError, ValueError) as e:
        print(f"error: cannot read policies file: {e}", file=sys.stderr)
        return 2

    try:
        with open(args.chain) as f:
            chain_data = json.load(f)
    except (OSError, ValueError) as e:
        print(f"error: cannot read chain file: {e}", file=sys.stderr)
        return 2

    if not isinstance(raw_policies, dict) or not isinstance(chain_data, dict):
        print("error: malformed JSON (expected objects)", file=sys.stderr)
        return 2

    try:
        policies: Dict[str, VerbPolicy] = {
            name: _parse_policy(d) for name, d in raw_policies.items()
        }
        chain: List[ChainStep] = [_parse_step(d) for d in chain_data.get("steps", [])]
        initial = _parse_classification(args.initial_classification)
        clusters: Dict[str, str] = {}
        if args.clusters:
            with open(args.clusters) as f:
                clusters = _parse_clusters(json.load(f))
    except (KeyError, ValueError) as e:
        print(f"error: invalid policy or chain: {e}", file=sys.stderr)
        return 2

    mode = (
        CompositionMode.CLEARANCE
        if args.mode == "clearance"
        else CompositionMode.TAINT
    )
    gate = create_gate(
        policies=policies,
        composition_mode=mode,
        initial_classification=initial,
        clusters=clusters,
    )

    verdict = gate.check_chain(chain)

    payload: Dict[str, Any] = {
        "action": verdict.action.value,
        "reasons": [r.value for r in verdict.reasons],
        "chain_classification": (
            verdict.chain_classification.value
            if verdict.chain_classification is not None
            else None
        ),
        "cluster_set": list(verdict.cluster_set),
        "clearance_violations": list(verdict.clearance_violations),
        "mode": mode.value,
        "initial_classification": initial.value,
        "chain_digest": verdict.digest,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    elif args.summary:
        c_eff = payload["chain_classification"]
        n_violations = len(payload["clearance_violations"])
        print(
            f"action={verdict.action.value} c_eff={c_eff} "
            f"mode={mode.value} violations={n_violations}"
        )
    else:
        print(f"Mode:              {mode.value}")
        print(f"Initial:           {initial.value}")
        print(f"Chain C_eff:       {payload['chain_classification']}")
        print(f"Cluster set:       {sorted(set(payload['cluster_set']))}")
        print(f"Clearance check:   "
              f"{'PASS' if not payload['clearance_violations'] else 'FAIL'}")
        if payload["clearance_violations"]:
            print(f"Violations:        {payload['clearance_violations']}")
        print(f"Verdict:           {verdict.action.value}")
        if verdict.reasons:
            print(f"Reasons:           "
                  f"{[r.value for r in verdict.reasons]}")
        if DenyReason.CLEARANCE_LEVEL_INSUFFICIENT in verdict.reasons:
            print("  (under-classified verb detected; chain denied)")
        elif DenyReason.CLEARANCE_CLUSTER_MISMATCH in verdict.reasons:
            print("  (cluster mismatch detected; chain denied)")
        print(f"Chain digest:      {verdict.digest}")

    if verdict.action == ChainAction.ALLOW:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
