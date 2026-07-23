"""Create, sign, and verify review-only CAGE-1 operator decisions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from core.cage1_decision import (
    create_operator_decision,
    sign_operator_decision,
    verify_operator_decision,
    write_operator_decision,
    write_signed_decision,
)
from core.signed_advisory_envelope import EnvelopeConfig, KeyRegistry, envelope_from_json, envelope_to_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cli.cage1_decision", description="Manage signed, review-only CAGE-1 operator decisions.")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Create an unsigned accept/reject/defer record.")
    create.add_argument("--advisory", required=True, help="Advisory JSON path.")
    create.add_argument("--decision", required=True, choices=("accept", "reject", "defer"))
    create.add_argument("--operator-id", required=True)
    create.add_argument("--rationale", default="")
    create.add_argument("--decided-at", type=float)
    create.add_argument("--out", required=True)

    sign = sub.add_parser("sign", help="Sign an existing decision record with HMAC-SHA256.")
    sign.add_argument("--decision", required=True, help="Unsigned decision JSON path.")
    sign.add_argument("--key-id", required=True)
    sign.add_argument("--hmac-secret", required=True)
    sign.add_argument("--hmac-secret-hex", action="store_true")
    sign.add_argument("--issued-at", type=float)
    sign.add_argument("--out", required=True)

    verify = sub.add_parser("verify", help="Verify a signed decision envelope.")
    verify.add_argument("--envelope", required=True)
    verify.add_argument("--key-id", required=True)
    verify.add_argument("--hmac-secret", required=True)
    verify.add_argument("--hmac-secret-hex", action="store_true")
    verify.add_argument("--now", type=float)

    return parser


def _read_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _secret(args: argparse.Namespace) -> bytes:
    if args.hmac_secret_hex:
        return bytes.fromhex(args.hmac_secret)
    return args.hmac_secret.encode("utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "create":
            record = create_operator_decision(
                _read_json(args.advisory),
                args.decision,
                args.operator_id,
                rationale=args.rationale,
                decided_at=args.decided_at,
            )
            write_operator_decision(record, args.out)
            print(record.to_json())
            return 0
        if args.command == "sign":
            from core.cage1_decision import OperatorDecision

            record = OperatorDecision.from_dict(_read_json(args.decision))
            envelope = sign_operator_decision(
                record,
                args.key_id,
                _secret(args),
                config=EnvelopeConfig(issued_at=args.issued_at),
                now=args.issued_at,
            )
            write_signed_decision(envelope, args.out)
            print(envelope_to_json(envelope, indent=2))
            return 0
        envelope = envelope_from_json(Path(args.envelope).read_text(encoding="utf-8"))
        registry = KeyRegistry()
        registry.register(args.key_id, _secret(args))
        result = verify_operator_decision(envelope, registry, now=args.now)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0 if result.valid else 1
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
