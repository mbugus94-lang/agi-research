"""Sign / verify an AIBOM advisory envelope.

Closes the 2026-07-06 AIBOM carryover. The AIBOM advisory emitter
produces a content-addressed JSON advisory. This CLI is the second
half of the handoff: it wraps that advisory in a SignedEnvelope,
so the agent gateway / human reviewer can verify the advisory has
not been tampered with between emission and review.

Subcommands:
  sign     Sign an advisory (JSON file or stdin) and emit an envelope.
  verify   Verify an envelope (JSON file or stdin) against a key.
  keygen   Generate an Ed25519 keypair and write PEM-style files.
  info     Print envelope metadata without verifying.

Examples:

  # Sign with HMAC-SHA256 (symmetric)
  python -m cli.sign_advisory sign \\
      --advisory advisory.json \\
      --key-id hmac-key-1 \\
      --hmac-secret "$(openssl rand -hex 32)" \\
      --out envelope.json

  # Sign with Ed25519 (asymmetric)
  python -m cli.sign_advisory sign \\
      --advisory advisory.json \\
      --key-id ed25519-key-1 \\
      --private-key priv.pem \\
      --out envelope.json

  # Verify an envelope
  python -m cli.sign_advisory verify \\
      --envelope envelope.json \\
      --hmac-secret "$(cat secret.txt)" \\
      --summary

  # Generate an Ed25519 keypair
  python -m cli.sign_advisory keygen \\
      --prefix myorg \\
      --out-dir ./keys
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Ensure repo root is on sys.path so `core.*` imports work
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.signed_advisory_envelope import (  # noqa: E402
    EnvelopeConfig,
    EnvelopeVerification,
    KeyRegistry,
    SignatureAlgorithm,
    SignedEnvelope,
    VerificationStatus,
    envelope_from_json,
    envelope_to_json,
    generate_ed25519_keypair,
    payload_digest,
    sign_aibom_advisory,
    sign_envelope,
    verify_envelope,
)


# ===========================================================================
# Args parsing
# ===========================================================================


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sign_advisory",
        description="Sign / verify an AIBOM advisory envelope.",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    # ---- sign ----
    p_sign = sub.add_parser("sign", help="Sign an advisory into an envelope.")
    p_sign.add_argument("--advisory", required=True, help="Path to advisory JSON file (or '-' for stdin).")
    p_sign.add_argument("--key-id", required=True, help="Signing key identifier (free-form).")
    p_sign.add_argument(
        "--hmac-secret",
        default=None,
        help="HMAC-SHA256 secret (hex or utf-8). Use for symmetric signing.",
    )
    p_sign.add_argument(
        "--hmac-secret-hex",
        action="store_true",
        help="Interpret --hmac-secret as hex (default: utf-8 bytes).",
    )
    p_sign.add_argument(
        "--private-key",
        default=None,
        help="Path to Ed25519 private key (PEM). Use for asymmetric signing.",
    )
    p_sign.add_argument(
        "--shape",
        choices=["envelope", "detached", "cosign"],
        default="envelope",
        help="Envelope shape (default: envelope).",
    )
    p_sign.add_argument(
        "--not-before",
        type=float,
        default=None,
        help="Unix timestamp the envelope becomes valid (optional).",
    )
    p_sign.add_argument(
        "--expires-at",
        type=float,
        default=None,
        help="Unix timestamp the envelope expires (optional).",
    )
    p_sign.add_argument(
        "--metadata",
        default=None,
        help="JSON string of metadata to embed in the envelope.",
    )
    p_sign.add_argument("--out", default="-", help="Output path (default: stdout).")
    p_sign.add_argument("--summary", action="store_true", help="Print summary to stderr.")
    p_sign.add_argument("--silent", action="store_true", help="Suppress all stdout output (envelope still written if --out is set).")

    # ---- verify ----
    p_verify = sub.add_parser("verify", help="Verify a signed envelope.")
    p_verify.add_argument("--envelope", required=True, help="Path to envelope JSON file (or '-' for stdin).")
    p_verify.add_argument(
        "--hmac-secret",
        default=None,
        help="HMAC-SHA256 secret (hex or utf-8).",
    )
    p_verify.add_argument(
        "--hmac-secret-hex",
        action="store_true",
        help="Interpret --hmac-secret as hex (default: utf-8 bytes).",
    )
    p_verify.add_argument(
        "--public-key",
        default=None,
        help="Path to Ed25519 public key (PEM).",
    )
    p_verify.add_argument(
        "--key-id",
        default=None,
        help="Single key_id to resolve (for in-process KeyRegistry use).",
    )
    p_verify.add_argument(
        "--key-map",
        default=None,
        help='JSON file mapping key_id to {"algorithm": "...", "key": "..."} for a static registry.',
    )
    p_verify.add_argument(
        "--payload",
        default=None,
        help="Path to payload JSON for DETACHED envelopes (required for detached).",
    )
    p_verify.add_argument(
        "--now",
        type=float,
        default=None,
        help="Override 'now' for freshness checks (test hook).",
    )
    p_verify.add_argument("--summary", action="store_true", help="Print summary to stderr.")
    p_verify.add_argument("--table", action="store_true", help="Print a one-row table of envelope fields.")
    p_verify.add_argument("--silent", action="store_true", help="Suppress summary output.")

    # ---- keygen ----
    p_keygen = sub.add_parser("keygen", help="Generate an Ed25519 keypair.")
    p_keygen.add_argument("--prefix", default="key", help="Key id prefix (default: key).")
    p_keygen.add_argument("--out-dir", required=True, help="Directory to write priv.pem / pub.pem / key_id.txt.")
    p_keygen.add_argument("--summary", action="store_true", help="Print key id and paths to stdout.")
    p_keygen.add_argument("--silent", action="store_true", help="Suppress output (used in tests).")

    # ---- info ----
    p_info = sub.add_parser("info", help="Print envelope metadata without verifying.")
    p_info.add_argument("--envelope", required=True, help="Path to envelope JSON file (or '-' for stdin).")
    p_info.add_argument("--summary", action="store_true", help="Print summary to stdout.")
    p_info.add_argument("--table", action="store_true", help="Print a one-row table of envelope fields.")
    p_info.add_argument("--silent", action="store_true", help="Suppress output (used in tests).")

    return parser


# ===========================================================================
# Helpers
# ===========================================================================


def _load_advisory(path: str) -> Dict[str, Any]:
    if path == "-":
        return json.loads(sys.stdin.read())
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_envelope(path: str) -> SignedEnvelope:
    if path == "-":
        return envelope_from_json(sys.stdin.read())
    with open(path, "r", encoding="utf-8") as f:
        return envelope_from_json(f.read())


def _write_envelope(envelope: SignedEnvelope, path: str) -> None:
    s = envelope_to_json(envelope, indent=2)
    if path == "-":
        sys.stdout.write(s)
        sys.stdout.write("\n")
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(s)
            f.write("\n")


def _resolve_hmac_secret(secret: str, *, hex_mode: bool) -> bytes:
    if hex_mode:
        try:
            return bytes.fromhex(secret)
        except ValueError as exc:
            raise SystemExit(f"--hmac-secret is not valid hex: {exc}")
    return secret.encode("utf-8")


def _load_pem_private_key(path: str):
    """Load an Ed25519 private key from a PEM file (cryptography lib)."""
    try:
        from cryptography.hazmat.primitives import serialization
    except ImportError as exc:
        raise SystemExit(
            "Ed25519 signing requires the `cryptography` package. "
            "Install with: pip install cryptography"
        ) from exc
    with open(path, "rb") as f:
        data = f.read()
    return serialization.load_pem_private_key(data, password=None)


def _load_pem_public_key(path: str):
    """Load an Ed25519 public key from a PEM file (cryptography lib)."""
    try:
        from cryptography.hazmat.primitives import serialization
    except ImportError as exc:
        raise SystemExit(
            "Ed25519 verification requires the `cryptography` package. "
            "Install with: pip install cryptography"
        ) from exc
    with open(path, "rb") as f:
        data = f.read()
    return serialization.load_pem_public_key(data)


def _build_resolver_from_map(
    key_map_path: str,
) -> Tuple[KeyRegistry, Dict[str, str]]:
    """Build a KeyRegistry from a JSON key map.

    The JSON shape:
        {
          "hmac-key-1": {"algorithm": "hmac-sha256", "key": "<hex>"},
          "ed25519-key-1": {"algorithm": "ed25519", "key": "/path/to/pub.pem"}
        }
    """
    with open(key_map_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    reg = KeyRegistry()
    algorithms: Dict[str, str] = {}
    for key_id, spec in raw.items():
        algo = spec.get("algorithm", "").lower()
        key_value = spec.get("key", "")
        if algo == "hmac-sha256":
            try:
                reg.register(key_id, bytes.fromhex(key_value))
            except ValueError:
                reg.register(key_id, key_value.encode("utf-8"))
        elif algo == "ed25519":
            reg.register(key_id, _load_pem_public_key(key_value))
        else:
            raise SystemExit(f"unsupported algorithm in key map for {key_id!r}: {algo!r}")
        algorithms[key_id] = algo
    return reg, algorithms


def _build_resolver_from_args(
    hmac_secret: Optional[str],
    hmac_secret_hex: bool,
    public_key_path: Optional[str],
    key_id: Optional[str],
) -> Tuple[KeyRegistry, Optional[str]]:
    """Build a single-key KeyRegistry from CLI args.

    Returns (registry, declared_algorithm) where declared_algorithm is
    the algorithm the operator *expects* for the key_id (used to
    sanity-check the envelope).
    """
    reg = KeyRegistry()
    declared = None
    if hmac_secret is not None:
        if key_id is None:
            raise SystemExit("--key-id is required when using --hmac-secret")
        secret = _resolve_hmac_secret(hmac_secret, hex_mode=hmac_secret_hex)
        reg.register(key_id, secret)
        declared = SignatureAlgorithm.HMAC_SHA256.value
    if public_key_path is not None:
        if key_id is None:
            raise SystemExit("--key-id is required when using --public-key")
        reg.register(key_id, _load_pem_public_key(public_key_path))
        declared = SignatureAlgorithm.ED25519.value
    if not reg:
        raise SystemExit("no keys provided (use --hmac-secret or --public-key)")
    return reg, declared


# ===========================================================================
# Subcommand handlers
# ===========================================================================


def cmd_sign(args: argparse.Namespace) -> int:
    advisory = _load_advisory(args.advisory)

    # Resolve signing key + algorithm
    metadata: Dict[str, Any] = {}
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"--metadata is not valid JSON: {exc}")
    # If user provided a payload dict, merge any _secondary_key metadata
    # from the advisory itself (none expected, but keep the door open).
    if isinstance(advisory, dict) and "_envelope_metadata" in advisory:
        for k, v in advisory["_envelope_metadata"].items():
            if k not in metadata:
                metadata[k] = v

    config = EnvelopeConfig(
        shape=args.shape,
        not_before=args.not_before,
        expires_at=args.expires_at,
        metadata=metadata,
    )

    if args.private_key is not None:
        priv = _load_pem_private_key(args.private_key)
        config.algorithm = SignatureAlgorithm.ED25519.value
        envelope = sign_envelope(advisory, args.key_id, priv, config=config)
    elif args.hmac_secret is not None:
        secret = _resolve_hmac_secret(args.hmac_secret, hex_mode=args.hmac_secret_hex)
        config.algorithm = SignatureAlgorithm.HMAC_SHA256.value
        envelope = sign_envelope(advisory, args.key_id, secret, config=config)
    else:
        raise SystemExit("must provide either --hmac-secret or --private-key")

    # Write
    if not args.silent and args.out == "-":
        # We will write to stdout below; summary goes to stderr.
        pass
    _write_envelope(envelope, args.out)

    if args.summary and not args.silent:
        sys.stderr.write(
            f"signed: key_id={envelope.key_id} algorithm={envelope.algorithm} "
            f"shape={envelope.shape} payload_digest={envelope.payload_digest[:16]}... "
            f"advisory_id={advisory.get('advisory_id', '?')[:16]}...\n"
        )

    # Exit codes:
    #   0 = signed OK
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    envelope = _load_envelope(args.envelope)

    # Build resolver
    if args.key_map is not None:
        resolver, declared_algorithms = _build_resolver_from_map(args.key_map)
        if envelope.key_id in declared_algorithms:
            declared = declared_algorithms[envelope.key_id]
        else:
            declared = None
    else:
        resolver, declared = _build_resolver_from_args(
            args.hmac_secret, args.hmac_secret_hex, args.public_key, args.key_id,
        )

    # Optional payload for DETACHED
    payload: Optional[Dict[str, Any]] = None
    if args.payload is not None:
        payload = _load_advisory(args.payload)

    result = verify_envelope(envelope, resolver, payload=payload, now=args.now)

    if args.summary and not args.silent:
        sys.stderr.write(
            f"verified: status={result.status} reason={result.reason!r} "
            f"key_id={result.key_id} algorithm={result.algorithm}\n"
        )
    if args.table and not args.silent:
        _print_envelope_table(envelope, result)

    # Exit codes:
    #   0 = valid
    #   1 = invalid signature / payload / freshness
    #   2 = malformed / unknown key / unknown algorithm
    if result.status == VerificationStatus.VALID.value:
        return 0
    if result.status in {
        VerificationStatus.INVALID_SIGNATURE.value,
        VerificationStatus.PAYLOAD_MISMATCH.value,
        VerificationStatus.EXPIRED.value,
        VerificationStatus.NOT_YET_VALID.value,
    }:
        return 1
    return 2


def cmd_keygen(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    priv, pub = generate_ed25519_keypair()
    key_id = f"{args.prefix}-{payload_digest({'k': id(priv)})[:12]}"

    try:
        from cryptography.hazmat.primitives import serialization
    except ImportError as exc:
        raise SystemExit(
            "Ed25519 keygen requires the `cryptography` package. "
            "Install with: pip install cryptography"
        ) from exc

    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv_path = out_dir / f"{key_id}.priv.pem"
    pub_path = out_dir / f"{key_id}.pub.pem"
    key_id_path = out_dir / f"{key_id}.key_id.txt"
    priv_path.write_bytes(priv_pem)
    pub_path.write_bytes(pub_pem)
    key_id_path.write_text(key_id + "\n", encoding="utf-8")

    if args.summary and not args.silent:
        sys.stdout.write(
            json.dumps(
                {
                    "key_id": key_id,
                    "private_key_path": str(priv_path),
                    "public_key_path": str(pub_path),
                    "key_id_path": str(key_id_path),
                    "algorithm": SignatureAlgorithm.ED25519.value,
                },
                indent=2,
                sort_keys=True,
            )
        )
        sys.stdout.write("\n")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    envelope = _load_envelope(args.envelope)
    if args.summary and not args.silent:
        sys.stdout.write(
            json.dumps(
                {
                    "schema_version": envelope.schema_version,
                    "shape": envelope.shape,
                    "algorithm": envelope.algorithm,
                    "key_id": envelope.key_id,
                    "payload_digest": envelope.payload_digest,
                    "issued_at": envelope.issued_at,
                    "not_before": envelope.not_before,
                    "expires_at": envelope.expires_at,
                    "has_cosign": envelope.cosign_signature is not None,
                    "metadata_keys": sorted(envelope.metadata.keys()),
                },
                indent=2,
                sort_keys=True,
            )
        )
        sys.stdout.write("\n")
    if args.table and not args.silent:
        # Use a fake verification result of "not verified"
        fake = EnvelopeVerification(
            status="not_verified",
            reason="info-only",
            key_id=envelope.key_id,
            algorithm=envelope.algorithm,
            payload_digest=envelope.payload_digest,
            verified_at=0.0,
            payload=envelope.payload,
        )
        _print_envelope_table(envelope, fake)
    return 0


# ===========================================================================
# Pretty-print
# ===========================================================================


def _print_envelope_table(envelope: SignedEnvelope, result: EnvelopeVerification) -> None:
    fields = [
        ("schema_version", envelope.schema_version),
        ("shape", envelope.shape),
        ("algorithm", envelope.algorithm),
        ("key_id", envelope.key_id),
        ("payload_digest", envelope.payload_digest[:32] + "..."),
        ("signature", envelope.signature[:24] + "..."),
        ("cosign", envelope.cosign_signature[:24] + "..." if envelope.cosign_signature else "(none)"),
        ("issued_at", str(envelope.issued_at)),
        ("not_before", str(envelope.not_before) if envelope.not_before is not None else "(none)"),
        ("expires_at", str(envelope.expires_at) if envelope.expires_at is not None else "(none)"),
        ("verification_status", result.status),
        ("verification_reason", result.reason),
    ]
    w = max(len(k) for k, _ in fields)
    sys.stdout.write("envelope:\n")
    for k, v in fields:
        sys.stdout.write(f"  {k.ljust(w)}  {v}\n")


# ===========================================================================
# main
# ===========================================================================


def main(argv: Optional[list] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.subcommand == "sign":
        return cmd_sign(args)
    if args.subcommand == "verify":
        return cmd_verify(args)
    if args.subcommand == "keygen":
        return cmd_keygen(args)
    if args.subcommand == "info":
        return cmd_info(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
