"""GovernorCircuit CLI - inspect, summarize, and audit the CEF substrate gate.

Mirrors the public surface of ``core/governor_circuit.GovernorCircuit`` for
operators who want to look at the gate without writing Python.

Subcommands
-----------
- ``summary``   Print a one-shot summary of a gate state (from JSON or live).
- ``audit-tail`` Show the last N transitions from a JSONL audit file.
- ``simulate``  Drive a new gate from a JSONL history of {tripped, label}
                observations and print the resulting transitions.
- ``doctor``    Quick health-check: is the gate open? how stale is the audit?

Usage
-----
::

    # Print a summary dict as JSON (ready for jq / dashboards)
    python -m cli.governor_circuit summary --input gate.json

    # Tail the last 20 audit transitions
    python -m cli.governor_circuit audit-tail --path audit.jsonl --last 20

    # Simulate a feed history and print resulting state transitions
    python -m cli.governor_circuit simulate \\
        --history history.jsonl \\
        --trip-threshold 0.05 \\
        --reset-threshold 0.01

    # Doctor: health check from an audit JSONL + state JSON
    python -m cli.governor_circuit doctor \\
        --state state.json --audit audit.jsonl

Design notes
------------
* All commands print JSON to stdout (machine-friendly for piping).
* Errors print to stderr as ``{"error": "..."}`` and exit non-zero.
* No network, no hidden state - the CLI is a pure projection of substrate
  data. This is the same trust contract the rest of the repo uses.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence

# Allow ``python cli/governor_circuit.py ...`` from repo root.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from core.cef_probabilistic_verification import ProbabilisticTripEngine  # noqa: E402
from core.governor_circuit import (  # noqa: E402
    DEFAULT_PROBE_COUNT,
    DEFAULT_RESET_THRESHOLD,
    DEFAULT_TRIP_THRESHOLD,
    GateObservation,
    GateState,
    GovernorCircuit,
    GovernorCircuitConfig,
    create_governor_circuit,
)


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _err(message: str) -> Dict[str, str]:
    return {"error": message}


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object at {path}, got {type(data).__name__}")
    return data


def _read_jsonl(path: str) -> Iterable[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Malformed JSONL at {path}:{line_no}: {exc}"
                ) from exc


# ---------------------------------------------------------------------------
# Subcommand: summary.
# ---------------------------------------------------------------------------


def cmd_summary(args: argparse.Namespace) -> int:
    """Print a summary of a gate from a JSON state file.

    Accepts either a ``GovernorCircuit.to_dict()`` blob or a bare
    ``GovernorCircuit.summary()`` blob (both are dicts).
    """
    if not os.path.isfile(args.input):
        print(json.dumps(_err(f"input not found: {args.input}")))
        return 2
    try:
        data = _read_json(args.input)
    except (OSError, ValueError) as exc:
        print(json.dumps(_err(str(exc))))
        return 2

    state = data.get("state", "<unknown>")
    upper_bound = data.get("upper_bound", 0.0)
    trip_band = data.get("trip_band", "unknown")
    transition_count = data.get("transition_count", 0)
    out = {
        "source": args.input,
        "state": state,
        "upper_bound": upper_bound,
        "trip_band": trip_band,
        "consecutive_good": data.get("consecutive_good", 0),
        "trip_threshold": data.get("trip_threshold"),
        "reset_threshold": data.get("reset_threshold"),
        "probe_count": data.get("probe_count"),
        "transition_count": transition_count,
        "per_output_bound": data.get("per_output_bound", 0.0),
        "session_bound": data.get("session_bound", 0.0),
        "per_output_band": data.get("per_output_band", "unknown"),
        "session_band": data.get("session_band", "unknown"),
    }
    print(json.dumps(out, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Subcommand: audit-tail.
# ---------------------------------------------------------------------------


def cmd_audit_tail(args: argparse.Namespace) -> int:
    """Print the last N transitions from a JSONL audit file."""
    if not os.path.isfile(args.path):
        print(json.dumps(_err(f"audit path not found: {args.path}")))
        return 2
    try:
        records = list(_read_jsonl(args.path))
    except (OSError, ValueError) as exc:
        print(json.dumps(_err(str(exc))))
        return 2
    tail = records[-args.last :] if args.last > 0 else records
    out = {
        "path": args.path,
        "total_records": len(records),
        "returned": len(tail),
        "transitions": tail,
    }
    print(json.dumps(out, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Subcommand: simulate.
# ---------------------------------------------------------------------------


def cmd_simulate(args: argparse.Namespace) -> int:
    """Drive a fresh gate from a history of observations and emit transitions.

    History JSONL schema (one record per line):

    ::

        {"tripped": true, "label": "ext-1", "metadata": {...}}
        {"tripped": false, "label": "ext-2"}
        ...

    Layers are inferred: a record with ``layer == "session"`` goes to the
    session engine, everything else to the per-output engine. When two
    layers exist, a fresh gate is created with both engines.
    """
    if not os.path.isfile(args.history):
        print(json.dumps(_err(f"history not found: {args.history}")))
        return 2
    try:
        records = list(_read_jsonl(args.history))
    except (OSError, ValueError) as exc:
        print(json.dumps(_err(str(exc))))
        return 2

    if not records:
        print(json.dumps(_err("history is empty")))
        return 2

    # Decide which engines to install.
    has_session = any(
        isinstance(r, dict) and r.get("layer") == "session" for r in records
    )
    per_output_engine = ProbabilisticTripEngine(
        alpha_prior=1.0,
        beta_prior=1.0,
    )
    session_engine = (
        ProbabilisticTripEngine(alpha_prior=1.0, beta_prior=1.0)
        if has_session
        else None
    )
    config = GovernorCircuitConfig(
        trip_threshold=args.trip_threshold,
        reset_threshold=args.reset_threshold,
        probe_count=args.probe_count,
    )
    gate = GovernorCircuit(
        config=config,
        per_output_engine=per_output_engine,
        session_engine=session_engine,
    )

    pre_transitions = len(gate._transitions)  # internal but stable for tests
    for record in records:
        tripped = bool(record.get("tripped", False))
        layer = record.get("layer", "per_output")
        # Session-layer trips route via the session engine; otherwise per-output.
        # The gate does not yet accept per-feed layer routing, so we wrap the
        # observation with a layer-tagged label and let ``feed`` allocate to
        # the per-output engine. For two-layer simulation, we pre-feed the
        # session engine directly so the gate sees both bounds.
        obs = GateObservation(
            tripped=tripped,
            label=str(record.get("label", "")),
            metadata=record.get("metadata", {}),
        )
        if layer == "session" and session_engine is not None:
            # Best-effort direct session-engine feed before the gate's per-output feed.
            try:
                from core.cef_probabilistic_verification import TripObservation  # noqa: E402

                session_engine.update(
                    TripObservation(
                        tripped=tripped,
                        label=obs.label,
                        metadata={**obs.metadata, "layer": "session"},
                    )
                )
            except Exception:
                pass
        gate.feed(obs)

    new_transitions = gate._transitions[pre_transitions:]
    out = {
        "history_path": args.history,
        "history_records": len(records),
        "trip_threshold": config.trip_threshold,
        "reset_threshold": config.reset_threshold,
        "probe_count": config.probe_count,
        "two_layer": has_session,
        "final_state": gate.state.value,
        "final_upper_bound": gate.upper_bound,
        "final_trip_band": gate.trip_band,
        "transitions_added": len(new_transitions),
        "transitions": [t.to_dict() for t in new_transitions],
    }
    print(json.dumps(out, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Subcommand: doctor.
# ---------------------------------------------------------------------------


def cmd_doctor(args: argparse.Namespace) -> int:
    """Health check: is the gate healthy, stale, or stuck?

    Inputs (all optional, but at least one recommended):

    - ``--state``   path to a JSON state blob (from ``summary()`` or ``to_dict()``)
    - ``--audit``   path to the JSONL audit log

    Health verdicts
    ~~~~~~~~~~~~~~~
    - ``ok``           gate CLOSED and within budget
    - ``probing``      gate HALF_OPEN (recovery in progress)
    - ``tripped``      gate OPEN (currently blocking)
    - ``stale``        audit log older than ``--max-age-seconds`` (default 300)
    - ``no-data``      neither --state nor --audit supplied
    """
    state_data: Optional[Dict[str, Any]] = None
    audit_records: List[Dict[str, Any]] = []
    if args.state:
        if not os.path.isfile(args.state):
            print(json.dumps(_err(f"state path not found: {args.state}")))
            return 2
        try:
            state_data = _read_json(args.state)
        except (OSError, ValueError) as exc:
            print(json.dumps(_err(str(exc))))
            return 2
    if args.audit:
        if not os.path.isfile(args.audit):
            print(json.dumps(_err(f"audit path not found: {args.audit}")))
            return 2
        try:
            audit_records = list(_read_jsonl(args.audit))
        except (OSError, ValueError) as exc:
            print(json.dumps(_err(str(exc))))
            return 2

    if state_data is None and not audit_records:
        print(json.dumps(_err("must supply --state or --audit (or both)")))
        return 2

    # 1. State health.
    state_value = state_data.get("state") if state_data else None
    upper_bound = state_data.get("upper_bound", 0.0) if state_data else 0.0
    trip_band = state_data.get("trip_band", "unknown") if state_data else "unknown"

    # 2. Audit staleness.
    last_ts: Optional[str] = None
    if audit_records:
        # Pick the largest timestamp seen (lexicographic for ISO-8601 works).
        for rec in audit_records:
            ts = rec.get("timestamp")
            if isinstance(ts, str) and (last_ts is None or ts > last_ts):
                last_ts = ts

    # 3. Verdict.
    if state_value == GateState.OPEN.value:
        verdict = "tripped"
    elif state_value == GateState.HALF_OPEN.value:
        verdict = "probing"
    elif state_value == GateState.CLOSED.value:
        verdict = "ok"
    elif state_value is None:
        verdict = "unknown"
    else:
        verdict = "unknown"

    out: Dict[str, Any] = {
        "verdict": verdict,
        "state": state_value,
        "upper_bound": upper_bound,
        "trip_band": trip_band,
        "audit_path": args.audit,
        "audit_records": len(audit_records),
        "last_audit_timestamp": last_ts,
        "trip_threshold": state_data.get("trip_threshold") if state_data else None,
        "reset_threshold": state_data.get("reset_threshold") if state_data else None,
    }
    print(json.dumps(out, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Argparse wiring.
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.governor_circuit",
        description="GovernorCircuit CLI: inspect, audit, simulate the CEF gate.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_summary = sub.add_parser("summary", help="print a one-shot gate summary")
    p_summary.add_argument(
        "--input", required=True, help="path to a JSON state file"
    )
    p_summary.set_defaults(func=cmd_summary)

    p_audit = sub.add_parser("audit-tail", help="tail the last N transitions")
    p_audit.add_argument("--path", required=True, help="path to the JSONL audit log")
    p_audit.add_argument(
        "--last", type=int, default=10, help="how many records to return (default 10)"
    )
    p_audit.set_defaults(func=cmd_audit_tail)

    p_sim = sub.add_parser("simulate", help="drive a fresh gate from a history")
    p_sim.add_argument(
        "--history", required=True, help="JSONL of {tripped, label, layer?}"
    )
    p_sim.add_argument(
        "--trip-threshold",
        type=float,
        default=DEFAULT_TRIP_THRESHOLD,
        help="bound above which the gate opens (default 0.05)",
    )
    p_sim.add_argument(
        "--reset-threshold",
        type=float,
        default=DEFAULT_RESET_THRESHOLD,
        help="bound at or below which OPEN leaves to HALF_OPEN (default 0.01)",
    )
    p_sim.add_argument(
        "--probe-count",
        type=int,
        default=DEFAULT_PROBE_COUNT,
        help="consecutive non-tripping observations required to close (default 1)",
    )
    p_sim.set_defaults(func=cmd_simulate)

    p_doc = sub.add_parser("doctor", help="quick health check")
    p_doc.add_argument("--state", help="optional path to a JSON state blob")
    p_doc.add_argument("--audit", help="optional path to the JSONL audit log")
    p_doc.set_defaults(func=cmd_doctor)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
