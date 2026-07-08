"""Drift signal CLI — PagerDuty-style AIOps primitive for signed advisories.

Closes the 2026-07-08 next-priority item:
  "Wire `envelope.timestamp` into a PagerDuty-style drift signal —
   `cli/drift_signal.py` reads a directory of envelopes and emits a
   CSV of `(envelope_id, key_id, age_seconds, status)` for AIOps
   ingestion."

Subcommands:
  scan     Scan a directory of signed envelopes and emit drift signal.

Examples:

  # Scan a directory with HMAC + Ed25519 keys
  python -m cli.drift_signal scan \\
      --envelopes-dir /var/lib/agi-research/envelopes \\
      --hmac-secret hmac.bin \\
      --ed25519-public-key key1.pub \\
      --csv /var/log/agi-research/drift.csv \\
      --json /var/log/agi-research/drift.json \\
      --summary

  # Scan with default config (HMAC secret from file, 1h stale threshold)
  python -m cli.drift_signal scan \\
      --envelopes-dir ./envelopes \\
      --hmac-secret-file secret.bin \\
      --summary
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# Ensure repo root is on sys.path so `core.*` imports work
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.drift_signal import (  # noqa: E402
    DEFAULT_STALE_THRESHOLD_SECONDS,
    DEFAULT_TRUSTED_ALGORITHMS,
    DriftConfig,
    DriftReport,
    scan_drift_signal,
    write_drift_report,
)
from core.signed_advisory_envelope import KeyRegistry  # noqa: E402


# ===========================================================================
# Args parsing
# ===========================================================================


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="drift_signal",
        description="PagerDuty-style drift signal for signed advisory envelopes.",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_scan = sub.add_parser("scan", help="Scan a directory of envelopes and emit drift signal.")
    p_scan.add_argument(
        "--envelopes-dir",
        required=True,
        help="Directory containing signed-envelope JSON files (recursive: *.json in dir).",
    )
    p_scan.add_argument(
        "--hmac-secret",
        default=None,
        help="HMAC-SHA256 secret (utf-8 string). Repeat for multiple HMAC keys.",
    )
    p_scan.add_argument(
        "--hmac-secret-hex",
        action="store_true",
        help="Interpret --hmac-secret as hex (default: utf-8 bytes).",
    )
    p_scan.add_argument(
        "--hmac-secret-file",
        default=None,
        help="Path to file containing the HMAC secret (raw bytes). Alternative to --hmac-secret.",
    )
    p_scan.add_argument(
        "--ed25519-public-key",
        action="append",
        default=[],
        help="Path to Ed25519 public key (PEM). Repeat for multiple keys. The --key-id is "
             "derived from the filename (without .pub extension).",
    )
    p_scan.add_argument(
        "--key-id",
        action="append",
        default=[],
        help="Optional explicit key_id for the matching --ed25519-public-key. Repeat to pair.",
    )
    p_scan.add_argument(
        "--stale-threshold",
        type=float,
        default=DEFAULT_STALE_THRESHOLD_SECONDS,
        help=f"Seconds; envelopes older than this get the STALE flag (default: {DEFAULT_STALE_THRESHOLD_SECONDS}).",
    )
    p_scan.add_argument(
        "--trusted-algorithms",
        default=",".join(sorted(DEFAULT_TRUSTED_ALGORITHMS)),
        help="Comma-separated list of trusted algorithm names (default: hmac-sha256,ed25519).",
    )
    p_scan.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="Follow symlinks when scanning the directory (default: no).",
    )
    p_scan.add_argument(
        "--now",
        type=float,
        default=None,
        help="Override the current time (unix timestamp). Useful for tests + replay.",
    )
    p_scan.add_argument(
        "--csv",
        default=None,
        help="Path to write the CSV drift signal. None = stdout if --json is also unset.",
    )
    p_scan.add_argument(
        "--json",
        dest="json_out",
        default=None,
        help="Path to write the JSON summary. None = stdout if --csv is also unset.",
    )
    p_scan.add_argument(
        "--summary",
        action="store_true",
        help="Print a one-line summary of the drift signal to stdout (counts + drift flags).",
    )
    p_scan.add_argument(
        "--exit-on-invalid",
        action="store_true",
        help="Exit with code 2 if any envelope is INVALID/EXPIRED/NOT_YET_VALID/MALFORMED. "
             "Useful for CI / AIOps gates. Default: exit 0.",
    )
    p_scan.add_argument(
        "--exit-on-drift",
        action="store_true",
        help="Exit with code 1 if any envelope has a DRIFT status. Useful for "
             "PagerDuty-style gates. Default: exit 0 (combine with --exit-on-invalid).",
    )

    return parser


# ===========================================================================
# Key resolution
# ===========================================================================


def _build_registry(args: argparse.Namespace) -> KeyRegistry:
    """Build a KeyRegistry from CLI args.

    HMAC: a single key_id (the basename of the secret file, or "hmac-default")
    Ed25519: one key_id per --ed25519-public-key, derived from the filename
             (without .pub) or supplied via --key-id.
    """
    registry = KeyRegistry()

    # --- HMAC ---
    hmac_secret: Optional[bytes] = None
    if args.hmac_secret_file:
        with open(args.hmac_secret_file, "rb") as f:
            hmac_secret = f.read()
        hmac_key_id = os.path.basename(args.hmac_secret_file)
    elif args.hmac_secret is not None:
        if args.hmac_secret_hex:
            hmac_secret = bytes.fromhex(args.hmac_secret)
        else:
            hmac_secret = args.hmac_secret.encode("utf-8")
        hmac_key_id = "hmac-cli"
    if hmac_secret is not None:
        registry.register(hmac_key_id, hmac_secret)

    # --- Ed25519 public keys ---
    ed_keys = list(args.ed25519_public_key or [])
    explicit_ids = list(args.key_id or [])
    if explicit_ids and len(explicit_ids) != len(ed_keys):
        print(
            f"error: --key-id must be paired with --ed25519-public-key (got "
            f"{len(explicit_ids)} ids for {len(ed_keys)} keys)",
            file=sys.stderr,
        )
        sys.exit(2)
    for i, pub_path in enumerate(ed_keys):
        from cryptography.hazmat.primitives.serialization import load_pem_public_key  # type: ignore
        with open(pub_path, "rb") as f:
            pub_pem = f.read()
        pub_key = load_pem_public_key(pub_pem)
        if explicit_ids:
            kid = explicit_ids[i]
        else:
            base = os.path.basename(pub_path)
            if base.endswith(".pub"):
                base = base[:-4]
            kid = base
        registry.register(kid, pub_key)

    return registry


# ===========================================================================
# Subcommand: scan
# ===========================================================================


def _cmd_scan(args: argparse.Namespace) -> int:
    if not os.path.isdir(args.envelopes_dir):
        print(f"error: --envelopes-dir is not a directory: {args.envelopes_dir}", file=sys.stderr)
        return 2

    registry = _build_registry(args)
    if not len(registry):
        print(
            "warning: no keys registered — every envelope will report UNKNOWN_KEY",
            file=sys.stderr,
        )

    trusted = frozenset(a.strip() for a in args.trusted_algorithms.split(",") if a.strip())
    config = DriftConfig(
        stale_threshold_seconds=float(args.stale_threshold),
        trusted_algorithms=trusted,
        follow_symlinks=bool(args.follow_symlinks),
        now=args.now,
    )

    report = scan_drift_signal(args.envelopes_dir, registry=registry, config=config)

    # --- Outputs ---
    wrote_any = False
    if args.csv:
        write_drift_report(report, csv_path=args.csv)
        wrote_any = True
    if args.json_out:
        write_drift_report(report, json_path=args.json_out)
        wrote_any = True
    if not wrote_any:
        # Default: print CSV to stdout (AIOps pipe-friendly)
        sys.stdout.write(report.to_csv())
        sys.stdout.flush()

    # --- Summary ---
    if args.summary:
        _print_summary(report, stream=sys.stderr)

    # --- Exit codes ---
    if args.exit_on_invalid and (
        report.n_invalid > 0 or report.n_expired > 0 or report.n_not_yet_valid > 0 or report.n_malformed > 0
    ):
        return 2
    if args.exit_on_drift and report.n_drift > 0:
        return 1
    return 0


def _print_summary(report: DriftReport, *, stream) -> None:
    """Print a one-line-per-flag summary to the given stream."""
    print(f"directory: {report.directory}", file=stream)
    print(f"n_envelopes: {report.n_envelopes}", file=stream)
    print(
        f"  valid={report.n_valid} drift={report.n_drift} invalid={report.n_invalid} "
        f"expired={report.n_expired} not_yet_valid={report.n_not_yet_valid} "
        f"malformed={report.n_malformed}",
        file=stream,
    )
    if report.drift_counts:
        print("drift_counts:", file=stream)
        for flag in sorted(report.drift_counts.keys()):
            print(f"  {flag}: {report.drift_counts[flag]}", file=stream)
    if report.first_encounter_keys:
        print(
            f"first_encounter_keys ({len(report.first_encounter_keys)}): "
            f"{', '.join(report.first_encounter_keys[:5])}"
            + ("..." if len(report.first_encounter_keys) > 5 else ""),
            file=stream,
        )
    if report.frequent_keys:
        print(
            f"frequent_keys ({len(report.frequent_keys)}): "
            f"{', '.join(report.frequent_keys[:5])}"
            + ("..." if len(report.frequent_keys) > 5 else ""),
            file=stream,
        )


# ===========================================================================
# Main
# ===========================================================================


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.subcommand == "scan":
        return _cmd_scan(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
