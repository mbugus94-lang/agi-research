"""Verify and join a CAGE-1 advisory, signed decisions, and raw evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from core.cage1_decision_consumer import (
    consume_operator_decision,
    consume_operator_decision_jsonl,
    write_consumer_report,
    write_decision_audit_jsonl,
)
from core.signed_advisory_envelope import EnvelopeError, KeyRegistry, envelope_from_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cli.cage1_consume", description="Verify-only CAGE-1 decision/evidence consumer.")
    parser.add_argument("--advisory", required=True, help="Advisory JSON path.")
    parser.add_argument("--raw-source", required=True, help="Preserved raw trend/fleet JSON path.")
    parser.add_argument("--envelope", action="append", help="Signed decision envelope path; repeat to inspect multiple decisions.")
    parser.add_argument("--decisions-jsonl", help="JSONL file of signed decision envelopes; every nonblank line is audited.")
    parser.add_argument("--audit-out", help="Write one machine-readable audit JSON object per JSONL decision line.")
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--hmac-secret", required=True)
    parser.add_argument("--hmac-secret-hex", action="store_true")
    parser.add_argument("--now", type=float)
    parser.add_argument("--out", help="Write the verification report JSON to this path.")
    return parser


def _json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _secret(args: argparse.Namespace) -> bytes:
    return bytes.fromhex(args.hmac_secret) if args.hmac_secret_hex else args.hmac_secret.encode("utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if not args.envelope and not args.decisions_jsonl:
        print("ERROR: provide --envelope or --decisions-jsonl", file=sys.stderr)
        return 2
    if args.envelope and args.decisions_jsonl:
        print("ERROR: --envelope and --decisions-jsonl are mutually exclusive", file=sys.stderr)
        return 2
    try:
        registry = KeyRegistry()
        registry.register(args.key_id, _secret(args))
        advisory = _json(args.advisory)
        raw_source = _json(args.raw_source)
        if args.decisions_jsonl:
            audit = consume_operator_decision_jsonl(
                advisory,
                Path(args.decisions_jsonl).read_text(encoding="utf-8"),
                registry,
                raw_source=raw_source,
                now=args.now,
            )
            report = audit.report
            if args.audit_out:
                write_decision_audit_jsonl(audit, args.audit_out)
        else:
            report = consume_operator_decision(
                advisory,
                [envelope_from_json(Path(path).read_text(encoding="utf-8")) for path in args.envelope],
                registry,
                raw_source=raw_source,
                now=args.now,
            )
        if args.out:
            write_consumer_report(report, args.out)
        print(report.to_json())
        return 0 if report.valid else 1
    except (EnvelopeError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
