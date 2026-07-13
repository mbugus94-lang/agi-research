"""
Contextual Least Privilege (CLP) CLI (arXiv:2607.08147, Prismata §3).

Operator-facing entry point for the read-side gate. The CLP gate is the
*integrity dual* of the write-side DSCC gate: where DSCC bounds what
data the agent can SEND (taint only grows), CLP bounds what data the
agent can READ (visibility only shrinks).

Together these two gates form the integrity/confidentiality duality of
agent information flow. A chain is admitted iff BOTH gates return
ALLOW. This CLI runs the read gate alone (for read-only audits) or both
gates (for full-duplex audits).

Usage:
    python -m cli.clp_check \\
        --capabilities caps.json \\
        --chain chain.json \\
        [--write-policies policies.json] \\
        [--initial-visibility secret] \\
        [--summary] [--json]

Exit codes:
    0 = chain passes (read gate, or both gates if --write-policies set)
    1 = chain fails
    2 = invalid input

Capabilities JSON format:
    {
      "read_env": {
        "name": "read_env",
        "required_label": "internal",
        "reads_untrusted_input": true,
        "emits_to_sink": false
      }
    }

Chain JSON format:
    {
      "steps": [
        {"verb_name": "read_env"},
        {"verb_name": "http_post_external"}
      ]
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

from core.contextual_least_privilege import (
    CLPAction,
    CLPReason,
    CapabilitySet,
    ContextualLeastPrivilegeGate,
    ReadCapability,
    VisibilityLabel,
    dual_gate_check,
)
from core.compositional_policy import (
    ChainAction,
    ChainStep,
    TaintSource,
    VerbPolicy,
    create_gate,
)


def _parse_visibility(value: Any) -> VisibilityLabel:
    if isinstance(value, VisibilityLabel):
        return value
    return VisibilityLabel(str(value).lower())


def _parse_taint(value: Any) -> TaintSource:
    if isinstance(value, TaintSource):
        return value
    return TaintSource(str(value).lower())


def _parse_capability(d: Dict[str, Any]) -> ReadCapability:
    return ReadCapability(
        name=d["name"],
        required_label=_parse_visibility(d.get("required_label", "internal")),
        reads_untrusted_input=bool(d.get("reads_untrusted_input", False)),
        emits_to_sink=bool(d.get("emits_to_sink", False)),
    )


def _parse_step(d: Dict[str, Any], taint_lookup: Dict[str, TaintSource] | None = None) -> ChainStep:
    raw = d.get("taint_in")
    if raw is None and taint_lookup is not None:
        raw = taint_lookup.get(d["verb_name"])
    if raw is None:
        raw = "internal"
    return ChainStep(
        verb_name=d["verb_name"],
        taint_in=_parse_taint(raw),
    )


def _parse_write_policy(d: Dict[str, Any]) -> VerbPolicy:
    return VerbPolicy(
        verb_name=d["verb_name"],
        taint_in=TaintSource(d.get("taint_in", "internal")),
    )


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="clp_check",
        description=(
            "Contextual Least Privilege gate (arXiv:2607.08147 Prismata §3). "
            "Optionally combines with the DSCC write gate (arXiv:2607.03423)."
        ),
    )
    parser.add_argument(
        "--capabilities", required=True, help="JSON file of ReadCapability entries"
    )
    parser.add_argument(
        "--chain", required=True, help="JSON file describing the proposed chain"
    )
    parser.add_argument(
        "--write-policies",
        default=None,
        help=(
            "Optional JSON file of write-side VerbPolicies. When supplied, "
            "the chain is also checked against the DSCC write gate; the "
            "chain is admitted only if BOTH gates return ALLOW."
        ),
    )
    parser.add_argument(
        "--initial-visibility",
        default="secret",
        help="Initial visibility for the chain (default: secret)",
    )
    parser.add_argument(
        "--summary", action="store_true", help="Print a one-line summary"
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit JSON instead of text"
    )
    args = parser.parse_args(argv)

    try:
        with open(args.capabilities) as f:
            raw_caps = json.load(f)
    except (OSError, ValueError) as e:
        print(f"error: cannot read capabilities file: {e}", file=sys.stderr)
        return 2
    try:
        with open(args.chain) as f:
            chain_data = json.load(f)
    except (OSError, ValueError) as e:
        print(f"error: cannot read chain file: {e}", file=sys.stderr)
        return 2

    if not isinstance(raw_caps, dict) or not isinstance(chain_data, dict):
        print("error: malformed JSON (expected objects)", file=sys.stderr)
        return 2

    # Load write policies up front (may be empty) so that the taint
    # lookup is always available for chain parsing.
    write_policies: Dict[str, VerbPolicy] = {}
    if args.write_policies:
        with open(args.write_policies) as f:
            raw_wp = json.load(f)
        write_policies = {
            name: _parse_write_policy(d) for name, d in raw_wp.items()
        }
    capabilities: Dict[str, ReadCapability] = {
        name: _parse_capability(d) for name, d in raw_caps.items()
    }
    # Taint-in may be omitted on the step itself if the verb has a
    # registered write policy (whose `taint_in` is the authoritative
    # source); fall back to ``internal`` otherwise.
    taint_lookup: Dict[str, TaintSource] = {
        name: _parse_taint(getattr(d, 'taint_in', TaintSource.INTERNAL))
        for name, d in write_policies.items()
    }
    # Also accept taint_in specified in capability files (operator's
    # intent for the read-side flow). Read-side taint is rare but
    # permitted as a fallback.
    for name, d in raw_caps.items():
        if name not in taint_lookup and "taint_in" in d:
            taint_lookup[name] = _parse_taint(d["taint_in"])
    chain: List[ChainStep] = [
        _parse_step(d, taint_lookup) for d in chain_data.get("steps", [])
    ]
    initial = _parse_visibility(args.initial_visibility)

    caps = CapabilitySet(capabilities=capabilities)
    read_gate = ContextualLeastPrivilegeGate(
        caps, initial_visibility=initial
    )

    write_verdict = None
    if write_policies:
        write_gate = create_gate(policies=write_policies)
        write_verdict, read_verdict, both_allow = dual_gate_check(
            chain, write_gate, read_gate
        )
    else:
        read_verdict = read_gate.check_chain(chain)
        both_allow = read_verdict.action == CLPAction.ALLOW

    payload: Dict[str, Any] = {
        "action": read_verdict.action.value,
        "reasons": [r.value for r in read_verdict.reasons],
        "visibility_at_each_step": [
            v.value for v in read_verdict.visibility_at_each_step
        ],
        "required_at_each_step": [
            v.value for v in read_verdict.required_at_each_step
        ],
        "capabilities_used": [c.to_dict() for c in read_verdict.capabilities_used],
        "labels_only_decrease": read_verdict.verify_labels_only_decrease(),
        "chain_digest": read_verdict.audit_digest,
    }
    if write_verdict is not None:
        payload["write"] = {
            "action": write_verdict.action.value,
            "reasons": [r.value for r in write_verdict.reasons],
        }
        payload["both_allow"] = both_allow

    if args.json:
        print(json.dumps(payload, indent=2))
    elif args.summary:
        n_reasons = len(read_verdict.reasons)
        if write_verdict is not None:
            print(
                f"read={read_verdict.action.value} write={write_verdict.action.value} "
                f"both_allow={both_allow} read_reasons={n_reasons}"
            )
        else:
            print(
                f"action={read_verdict.action.value} "
                f"labels_only_decrease={payload['labels_only_decrease']} "
                f"reasons={n_reasons}"
            )
    else:
        print(f"Initial visibility:  {initial.value}")
        print(f"Read verdict:        {read_verdict.action.value}")
        if read_verdict.reasons:
            print(f"Read reasons:        {[r.value for r in read_verdict.reasons]}")
        if write_verdict is not None:
            print(f"Write verdict:       {write_verdict.action.value}")
            if write_verdict.reasons:
                print(
                    f"Write reasons:       "
                    f"{[r.value for r in write_verdict.reasons]}"
                )
            print(f"Both admit:          {both_allow}")
            if not both_allow:
                if read_verdict.action != CLPAction.ALLOW:
                    print(
                        "  (read side rejected — visibility can only narrow;"
                        " narrowing past a verb's need is rejected)"
                    )
                if write_verdict.action != ChainAction.ALLOW:
                    print(
                        "  (write side rejected — taint can only grow;"
                        " growing past a verb's threshold is rejected)"
                    )
        else:
            print(
                f"Labels-only-decrease: {payload['labels_only_decrease']}"
            )
        print(f"Chain digest:        {read_verdict.audit_digest}")

    if read_verdict.action != CLPAction.ALLOW:
        return 1
    if write_verdict is not None and write_verdict.action != ChainAction.ALLOW:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
