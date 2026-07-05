"""CLI for running the Constraint Pressure Probe (CPP).

Usage:
    python -m cli.cpp_run --verbs pay,read --audit cpp.jsonl
    python -m cli.cpp_run --target-module my_pkg.targets:default_target --verbs pay
    python -m cli.cpp_run --json-out emergence.json --summary

Builds on skills/cpp.py (arXiv:2606.14831 progressive exit sealing protocol)
and the VerbPolicyBundle audit substrate (arXiv:2606.19390 AIBOM/CSAF-VEX).
The CLI is the operator-facing surface for the probe: it builds a
ConstraintPressureProbe, invokes the target, and prints a summary
(emergence_by_level, emergence_by_verb, worst_band, thanatosis_count).

Conservative posture:
  - The CLI does not auto-act on detections. The JSONL audit log is the
    replay trail; the operator decides what to do with a worst_band !=
    "none" outcome.
  - The target is supplied by the operator (--target-module or stdin).
    The probe never invokes a default target on its own; an unspecified
    target exits with a clear error.
"""

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from skills.cpp import (
    CPPConfig,
    CPPOutcome,
    ConstraintPressureProbe,
    DEFAULT_SCHEDULE,
    ProbeLevel,
    create_cpp_probe,
    run_cpp,
)


def _parse_verbs(arg: Optional[str]) -> tuple:
    if not arg:
        return ()
    return tuple(v.strip() for v in arg.split(",") if v.strip())


def _load_target(spec: Optional[str]):
    """Load a target callable from a 'module:attr' spec.

    Returns the callable or raises ValueError. The CLI intentionally does
    not provide a default target; an operator must opt in.
    """
    if not spec:
        raise ValueError(
            "no --target-module supplied. The probe refuses to invoke a "
            "default target; pass --target-module my.module:callable."
        )
    if ":" not in spec:
        raise ValueError(f"--target-module expects 'module:callable', got {spec!r}")
    module_name, attr = spec.split(":", 1)
    module = importlib.import_module(module_name)
    target = getattr(module, attr)
    if not callable(target):
        raise ValueError(f"{spec!r} resolved to non-callable {type(target).__name__}")
    return target


def _format_summary(outcome: CPPOutcome) -> str:
    lines: List[str] = []
    lines.append(f"Total observations: {outcome.total_observations}")
    lines.append(f"CEF substrate available: {outcome.cef_substrate_available}")
    lines.append(f"Worst band: {outcome.worst_band}")
    lines.append(f"Thanatosis (CET) count: {outcome.thanatosis_count}")
    lines.append("")
    lines.append("Emergence by level (HIGH+CRITICAL share):")
    for level_name, rate in outcome.emergence_by_level.items():
        lines.append(f"  {level_name:<32s} {rate:.2%}")
    lines.append("")
    if outcome.emergence_by_verb:
        lines.append("Emergence by verb (HIGH+CRITICAL share):")
        for verb, rate in outcome.emergence_by_verb.items():
            lines.append(f"  {verb:<32s} {rate:.2%}")
        lines.append("")
    if outcome.audit_path:
        lines.append(f"Audit log: {outcome.audit_path}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cli.cpp_run",
        description="Run the Constraint Pressure Probe (CPP) against a target.",
    )
    parser.add_argument(
        "--target-module",
        default=None,
        help="'module:callable' spec for the target. Required.",
    )
    parser.add_argument(
        "--verbs",
        default=None,
        help="Comma-separated verb names to probe. If empty, probe is "
        "run once per level with no verb namespace.",
    )
    parser.add_argument(
        "--audit",
        default=None,
        help="Path to write JSONL audit log.",
    )
    parser.add_argument(
        "--json-out",
        default=None,
        help="Path to write the outcome.to_dict() JSON.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print the human-readable summary to stdout.",
    )
    parser.add_argument(
        "--max-marker-count-for-clean",
        type=int,
        default=1,
        help="Max markers + LOW severity before promoting a detection to "
        "a non-clean band. Default: 1 (matches the default in CPPConfig).",
    )
    args = parser.parse_args(argv)

    target = _load_target(args.target_module)
    verbs = _parse_verbs(args.verbs)
    config = CPPConfig(
        verbs=verbs,
        audit_path=args.audit,
        max_marker_count_for_clean=args.max_marker_count_for_clean,
    )
    probe = ConstraintPressureProbe(config=config)
    outcome = probe.run(target, verbs=verbs)

    if args.summary:
        print(_format_summary(outcome))

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(outcome.to_dict(), indent=2, sort_keys=True))

    # Exit code: 0 = clean, 1 = any HIGH+, 2 = any CRITICAL (CET)
    if outcome.worst_band == "critical":
        return 2
    if outcome.worst_band in ("high", "medium"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
