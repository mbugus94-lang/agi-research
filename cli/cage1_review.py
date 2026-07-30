"""CLI for review-only CAGE-1 fleet/trend advisory projections."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Optional

from core.cage1_advisory import project_review_advisory, write_review_advisory
from core.cage1_decision_consumer import consume_operator_decision
from core.cage1_fleet import aggregate_fleet, load_fleet_snapshots
from core.cage1_trend import trend_fleet_snapshots
from core.signed_advisory_envelope import KeyRegistry, envelope_from_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cli.cage1_review", description="Emit a review-only CAGE-1 fleet advisory.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fleet-input", help="Ordered CAGE-1 snapshots as JSON array or JSONL.")
    source.add_argument("--compare-snapshot", action="append", help="Saved snapshot path; repeat at least twice.")
    source.add_argument("--trend-input", help="Saved CAGE-1 decision fleet trend JSON.")
    source.add_argument("--fixture", choices=("schema-invalid", "mixed-fleet", "multi-schema-invalid"), help="Run a deterministic review-only fixture.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--out", help="Write the advisory JSON to this path.")
    parser.add_argument("--decision-envelope", action="append", help="Signed operator decision envelope; repeat to verify multiple decisions.")
    parser.add_argument("--decision-key-id", help="Key ID used to verify signed operator decisions.")
    parser.add_argument("--decision-hmac-secret", help="HMAC secret used to verify signed operator decisions.")
    parser.add_argument("--decision-hmac-secret-hex", action="store_true", help="Interpret --decision-hmac-secret as hexadecimal bytes.")
    parser.add_argument("--decision-now", type=float, help="Verification timestamp for signed decision expiry checks.")
    parser.add_argument("--decision-report-out", help="Write the verification-only decision report JSON to this path.")
    parser.add_argument("--notes", default="")
    return parser


def _schema_invalid_fixture() -> dict[str, Any]:
    return {
        "category": "cage1_decision_fleet_audit",
        "schema_version": "1.0",
        "status": "invalid",
        "source_count": 1,
        "report_count": 1,
        "line_count": 1,
        "valid_line_count": 0,
        "invalid_line_count": 1,
        "status_counts": {"invalid_schema": 1},
        "decision_counts": {},
        "advisory_counts": {},
        "conflicting_advisories": [],
        "sources": [{"source_id": "fixture-member.jsonl"}],
        "lines": [{
            "category": "cage1_decision_audit_line",
            "schema_version": "9.9",
            "source_id": "fixture-member.jsonl",
            "source_line_number": 7,
            "status": "invalid_schema",
            "reason": "schema_version must be exactly '1.0'",
            "decision": None,
        }],
        "report_status_counts": {"invalid": 1},
        "decision_applied": False,
        "automatic_action_taken": False,
    }


def _mixed_fleet_fixture() -> dict[str, Any]:
    return {
        "category": "cage1_decision_fleet_audit",
        "schema_version": "1.0",
        "status": "invalid",
        "source_count": 2,
        "report_count": 2,
        "line_count": 2,
        "valid_line_count": 1,
        "invalid_line_count": 1,
        "status_counts": {"invalid_schema": 1, "valid": 1},
        "decision_counts": {"defer": 1},
        "advisory_counts": {"advisory-clean": 1},
        "conflicting_advisories": [],
        "sources": [{"source_id": "clean-member.jsonl"}, {"source_id": "drifted-member.jsonl"}],
        "lines": [
            {
                "category": "cage1_decision_audit_line",
                "schema_version": "1.0",
                "source_id": "clean-member.jsonl",
                "source_line_number": 3,
                "status": "valid",
                "advisory_digest": "advisory-clean",
                "envelope_digest": "envelope-clean",
                "decision": "defer",
                "operator_id": "operator-fixture",
                "reason": "verified",
            },
            {
                "category": "cage1_decision_audit_line",
                "schema_version": "9.9",
                "source_id": "drifted-member.jsonl",
                "source_line_number": 8,
                "status": "invalid_schema",
                "reason": "schema_version must be exactly '1.0'",
                "decision": None,
            },
        ],
        "report_status_counts": {"invalid": 1, "valid": 1},
        "decision_applied": False,
        "automatic_action_taken": False,
    }


def _multi_schema_invalid_fixture() -> dict[str, Any]:
    return {
        "category": "cage1_decision_fleet_audit",
        "schema_version": "1.0",
        "status": "invalid",
        "source_count": 3,
        "report_count": 3,
        "line_count": 3,
        "valid_line_count": 0,
        "invalid_line_count": 3,
        "status_counts": {"invalid_schema": 3},
        "decision_counts": {},
        "advisory_counts": {},
        "conflicting_advisories": [],
        "sources": [
            {"source_id": "member-z.jsonl"},
            {"source_id": "member-a.jsonl"},
            {"source_id": "member-m.jsonl"},
        ],
        "lines": [
            {
                "category": "cage1_decision_audit_line",
                "schema_version": "9.9",
                "source_id": "member-z.jsonl",
                "source_line_number": 12,
                "status": "invalid_schema",
                "reason": "schema_version must be exactly '1.0'",
                "decision": None,
            },
            {
                "category": "cage1_decision_audit_line",
                "schema_version": "1.0",
                "source_id": "member-a.jsonl",
                "source_line_number": 4,
                "status": "invalid_schema",
                "reason": "category must be exactly 'cage1_decision_audit_line'",
                "decision": None,
            },
            {
                "category": "wrong-category",
                "schema_version": "1.0",
                "source_id": "member-m.jsonl",
                "source_line_number": 19,
                "status": "invalid_schema",
                "reason": "category must be exactly 'cage1_decision_audit_line'",
                "decision": None,
            },
        ],
        "report_status_counts": {"invalid": 3},
        "decision_applied": False,
        "automatic_action_taken": False,
    }


def _load_source(args: argparse.Namespace) -> Any:
    if args.fixture:
        if args.fixture == "schema-invalid":
            return _schema_invalid_fixture()
        if args.fixture == "mixed-fleet":
            return _mixed_fleet_fixture()
        if args.fixture == "multi-schema-invalid":
            return _multi_schema_invalid_fixture()
    if args.fleet_input:
        return aggregate_fleet(load_fleet_snapshots(args.fleet_input), notes=args.notes)
    if args.trend_input:
        value = json.loads(open(args.trend_input, encoding="utf-8").read())
        if not isinstance(value, dict):
            raise ValueError("--trend-input must contain a JSON object")
        return value
    paths = args.compare_snapshot or []
    if len(paths) < 2:
        raise ValueError("--compare-snapshot requires at least two paths")
    snapshots = [json.loads(open(path, encoding="utf-8").read()) for path in paths]
    return trend_fleet_snapshots(snapshots, notes=args.notes)


def _decision_secret(args: argparse.Namespace) -> bytes:
    if args.decision_hmac_secret_hex:
        return bytes.fromhex(args.decision_hmac_secret or "")
    return (args.decision_hmac_secret or "").encode("utf-8")


def _verify_decisions(args: argparse.Namespace, advisory: Any, source: Any) -> Any:
    paths = args.decision_envelope or []
    if not paths:
        return None
    if not args.decision_key_id or args.decision_hmac_secret is None:
        raise ValueError("--decision-envelope requires --decision-key-id and --decision-hmac-secret")
    registry = KeyRegistry()
    registry.register(args.decision_key_id, _decision_secret(args))
    envelopes = [envelope_from_json(open(path, encoding="utf-8").read()) for path in paths]
    return consume_operator_decision(
        advisory,
        envelopes,
        registry,
        raw_source=source,
        now=args.decision_now,
    )


def main(argv: Optional[list[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        source = _load_source(args)
        advisory = project_review_advisory(source, notes=args.notes)
        decision_report = _verify_decisions(args, advisory, source)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.out:
        write_review_advisory(advisory, args.out)
    if decision_report is not None and args.decision_report_out:
        with open(args.decision_report_out, "w", encoding="utf-8") as handle:
            handle.write(decision_report.to_json() + "\n")
    if args.format == "markdown":
        print(advisory.to_markdown())
    elif decision_report is None:
        print(advisory.to_json())
    else:
        print(json.dumps({"advisory": advisory.to_dict(), "decision_verification": decision_report.to_dict()}, indent=2, sort_keys=True))
    if decision_report is not None and not decision_report.valid:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
