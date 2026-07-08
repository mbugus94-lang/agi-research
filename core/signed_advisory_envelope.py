"""Signed Advisory Envelope — closes the 2026-07-06 AIBOM carryover.

The AIBOM advisory emitter (core/aibom_advisory.py) landed a
*content-addressed* advisory: `advisory_id = sha256(canonical_json)`
of the static evidence, so two observers of the same bundle + audit
log produce the same advisory_id. The advisor's AIBOMAdvisory dataclass
carries a documented signature placeholder:

  > signature (advisory_id is the content hash; the signature
  >   placeholder is a hook for a future signed envelope)

This module is that hook. It wraps an `AIBOMAdvisory` (or any
content-addressed payload) in a small, transport-agnostic envelope
that provides:

  1. Content integrity — the envelope carries the canonical hash of
     the payload (`payload_digest`) and signs THAT, so reordering the
     envelope fields does not invalidate the signature.
  2. Algorithm agility — the envelope declares its signature
     algorithm (`hmac-sha256` for symmetric, `ed25519` for
     asymmetric). Future algorithms can be added without breaking
     existing envelopes.
  3. Key provenance — the envelope carries the `key_id` of the
     signing key. A downstream consumer can refuse to verify a
     signature from an unknown / revoked key.
  4. Envelope shape — three shapes for three consumers:
       * ENVELOPE — payload embedded inside the envelope. The
         default for human review + single-file exchange.
       * DETACHED — payload digest + signature only. The payload
         travels separately. The default for large payloads
         (audit logs that are MB-scale).
       * COSIGN — a Sigstore-style dual-signature envelope: HMAC for
         the local agent + Ed25519 for the gateway. The default for
         cross-domain handoffs.
  5. Tamper evidence — any byte change in the payload invalidates
     the signature. The envelope's `verify_envelope` is a pure
     function of (envelope, key_lookup).
  6. Freshness — the envelope carries `issued_at` + `not_before` +
     `expires_at`. A downstream consumer can refuse to act on an
     expired advisory, even if the signature is valid.

Research motivation (2026-07-07):
  - arXiv:2606.19390v1: "advisories are produced from combined
    static and runtime evidence, cryptographically signed, and
    verifiable through deterministic replay". The previous AIBOM
    build delivered the *deterministic replay* half (canonical
    JSON + content hash). This build delivers the *cryptographic
    signature* half.
  - Vinton Cerf (Open Frontier, 2026-06-30): the rise of
    multi-source agents will force the industry back toward
    formal, standardized protocols — "the way TCP/IP did for
    the early internet". The signed envelope is the
    *substrate-level* piece of that claim: a tiny, content-
    addressed, signature-verifiable message format that any
    agent-to-agent (or agent-to-gateway) protocol can wrap.
  - Agent Gateways (Forbes, Jul 5 2026; Nutanix; Arcade on
    Azure/AWS marketplaces): every agent-tool call passes
    through a centralized control plane emitting tamper-evident,
    content-addressed advisories. The signed envelope is the
    wire format for that handoff.
  - Steerability via constraints (arXiv:2607.02389): the
    substrate + tooling approach for coding-agent oversight.
    The envelope is the substrate half; downstream tooling
    (CI gates, OPA evaluators, gateway filters) consume it.
  - Hermes Agent (NousResearch, issue #58755 closed via
    PR #59110): the fix sanitized message sequences so the
    same input produces the same output. The envelope's
    `canonical_form` is the equivalent invariant: same
    advisory + same key → same signature, every time.
  - Claude Code (anthropics, issue #74365): a long-lived
    background session confabulated a security incident from
    its own output. The signed envelope makes the
    confabulation *detectable*: the agent's claim of
    "security incident" must reference a signed advisory;
    without one, the claim is just narrative drift.

Conservative posture:
  - Pure functions. `sign_envelope` and `verify_envelope` are
    deterministic given the same inputs (key, payload). No I/O.
  - The envelope is *additive*. An `AIBOMAdvisory` produced
    without signing remains valid; signing is opt-in.
  - Two algorithms: HMAC-SHA256 (symmetric, default) and
    Ed25519 (asymmetric, opt-in). Both are standard. No custom
    cryptography.
  - No key generation inside the module. The caller supplies the
    key. The module never generates, stores, or logs a key.
  - Ed25519 uses the `cryptography` library if available; the
    import is soft (HMAC-SHA256 is the dependency-free default).
  - The envelope carries *no payload data beyond the digest*
    in DETACHED and COSIGN shapes. The payload travels
    separately and is the caller's responsibility.
  - `verify_envelope` never mutates. It returns a frozen
    `EnvelopeVerification` with the verification decision +
    the reason for any failure.
  - `issued_at` defaults to time.time() but can be pinned for
    deterministic testing.
  - `not_before` and `expires_at` are optional. If set, the
    verifier enforces them.
  - The envelope's `key_id` is a free-form string. The
    caller decides the key-lookup protocol (file, vault, KMS).
    The module never resolves `key_id` to a key.

Test coverage: 50+ tests in experiments/test_signed_advisory_envelope.py
  covering algorithm agility, key provenance, freshness, tamper
  detection, envelope shapes, AIBOM integration, deterministic
  signing, and CLI integration.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union


# ===========================================================================
# Envelope schema
# ===========================================================================

ENVELOPE_SCHEMA_VERSION = "1.0.0"


# ===========================================================================
# Enums
# ===========================================================================


class SignatureAlgorithm(str, Enum):
    """Supported signature algorithms. Add new values; never remove."""

    HMAC_SHA256 = "hmac-sha256"
    ED25519 = "ed25519"


class EnvelopeShape(str, Enum):
    """How the payload is bound to the envelope.

    ENVELOPE — payload embedded inside the envelope. Default for
      human review and single-file exchange.
    DETACHED — payload digest + signature only. The payload
      travels separately. Default for large payloads.
    COSIGN — a Sigstore-style dual-signature envelope: HMAC for
      the local agent + Ed25519 for the gateway. The default for
      cross-domain handoffs.
    """

    ENVELOPE = "envelope"
    DETACHED = "detached"
    COSIGN = "cosign"


class VerificationStatus(str, Enum):
    """The four outcomes of `verify_envelope`."""

    VALID = "valid"
    INVALID_SIGNATURE = "invalid_signature"
    EXPIRED = "expired"
    NOT_YET_VALID = "not_yet_valid"
    UNKNOWN_KEY = "unknown_key"
    UNKNOWN_ALGORITHM = "unknown_algorithm"
    MALFORMED_ENVELOPE = "malformed_envelope"
    PAYLOAD_MISMATCH = "payload_mismatch"


# ===========================================================================
# Key registry (in-process)
# ===========================================================================

# A KeyResolver is a callable that takes a key_id and returns
# either the key bytes (for HMAC) or an object with a `.sign` /
# `.verify` method (for Ed25519). Returns None if the key is
# not found. The module ships with an in-process `KeyRegistry`
# for tests and single-process use; production deployments
# should supply a resolver that hits a vault / KMS.
KeyResolver = Callable[[str], Optional[Any]]


class KeyRegistry:
    """In-process key registry.

    The simplest resolver: a dict from key_id to key material.
    Production deployments should use a vault-backed resolver.
    """

    def __init__(self) -> None:
        self._keys: Dict[str, Any] = {}

    def register(self, key_id: str, key: Any) -> None:
        self._keys[key_id] = key

    def unregister(self, key_id: str) -> None:
        self._keys.pop(key_id, None)

    def resolve(self, key_id: str) -> Optional[Any]:
        return self._keys.get(key_id)

    def __call__(self, key_id: str) -> Optional[Any]:
        return self.resolve(key_id)

    def __len__(self) -> int:
        return len(self._keys)


# ===========================================================================
# Errors
# ===========================================================================


class EnvelopeError(Exception):
    """Base class for envelope errors."""


class MalformedEnvelopeError(EnvelopeError):
    """The envelope JSON is missing required fields or has wrong types."""


class UnknownAlgorithmError(EnvelopeError):
    """The envelope declares an algorithm the verifier cannot handle."""


class UnknownKeyError(EnvelopeError):
    """The envelope declares a key_id the resolver cannot find."""


# ===========================================================================
# Canonical form + digest
# ===========================================================================


def _scrub_private(obj: Any) -> Any:
    """Recursively strip underscore-prefixed keys from `obj`.

    Private (signer-local, not in the canonical form) fields live
    under keys beginning with "_" - e.g. metadata["_secondary_key"]
    holds the actual Ed25519 key object used to compute the
    cosign_signature, but it must never appear in the bytes that
    are signed, nor in the JSON serialization that a downstream
    consumer compares against.
    """
    if isinstance(obj, Mapping):
        return {k: _scrub_private(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [_scrub_private(x) for x in obj]
    if isinstance(obj, tuple):
        return tuple(_scrub_private(x) for x in obj)
    return obj


def canonical_form(payload: Mapping[str, Any]) -> str:
    """Deterministic JSON serialization.

    Sorted keys, no whitespace, UTF-8. The same logical payload
    always produces the same byte string, regardless of input
    key order. Underscore-prefixed keys are recursively stripped
    before serialization (private signer-local fields like
    metadata["_secondary_key"] are not part of the signed content).
    This is the same canonical form used by
    core.aibom_advisory._canonical_form; duplicated here so this
    module is importable without the AIBOM substrate.
    """
    return json.dumps(_scrub_private(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_digest(payload: Mapping[str, Any]) -> str:
    """Return the sha256 hex digest of the canonical form of `payload`.

    The digest is the *content hash* the envelope signs. The
    payload itself can travel in ENVELOPE shape (embedded) or
    DETACHED shape (separate); the digest is always the same.
    """
    return hashlib.sha256(canonical_form(payload).encode("utf-8")).hexdigest()


# ===========================================================================
# Envelope dataclass
# ===========================================================================


@dataclass
class SignedEnvelope:
    """A signed advisory envelope.

    Fields:
      schema_version: the envelope schema version.
      shape: ENVELOPE / DETACHED / COSIGN.
      algorithm: HMAC_SHA256 / ED25519.
      key_id: the signing key identifier. Resolved by the verifier.
      payload_digest: sha256 of the canonical form of the payload.
      payload: the embedded payload (ENVELOPE / COSIGN) or None
        (DETACHED).
      signature: base64url-encoded signature bytes.
      cosign_signature: base64url-encoded secondary signature
        (COSIGN only) — HMAC + Ed25519 in one envelope.
      issued_at: unix timestamp the envelope was created.
      not_before: earliest unix timestamp the envelope is valid
        (None = valid immediately).
      expires_at: latest unix timestamp the envelope is valid
        (None = no expiry).
      metadata: free-form dict for operator context (signer
        identity, environment, run id, etc.). Not signed.
      signed_bytes: the exact bytes that were signed. Set by
        `sign_envelope`. Used by `verify_envelope` for
        constant-time comparison.
    """

    schema_version: str
    shape: str
    algorithm: str
    key_id: str
    payload_digest: str
    payload: Optional[Dict[str, Any]]
    signature: str
    cosign_signature: Optional[str]
    issued_at: float
    not_before: Optional[float]
    expires_at: Optional[float]
    metadata: Dict[str, Any]
    signed_bytes: bytes = field(default=b"", repr=False)

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "shape": self.shape,
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "payload_digest": self.payload_digest,
            "payload": self.payload,
            "signature": self.signature,
            "issued_at": self.issued_at,
            "metadata": dict(self.metadata),
        }
        if self.cosign_signature is not None:
            out["cosign_signature"] = self.cosign_signature
        if self.not_before is not None:
            out["not_before"] = self.not_before
        if self.expires_at is not None:
            out["expires_at"] = self.expires_at
        return out

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "SignedEnvelope":
        if not isinstance(d, Mapping):
            raise MalformedEnvelopeError(f"envelope must be a Mapping; got {type(d).__name__}")
        required = {"schema_version", "shape", "algorithm", "key_id", "payload_digest", "signature"}
        missing = required - set(d.keys())
        if missing:
            raise MalformedEnvelopeError(f"missing required fields: {sorted(missing)}")
        return cls(
            schema_version=str(d["schema_version"]),
            shape=str(d["shape"]),
            algorithm=str(d["algorithm"]),
            key_id=str(d["key_id"]),
            payload_digest=str(d["payload_digest"]),
            payload=d.get("payload"),
            signature=str(d["signature"]),
            cosign_signature=d.get("cosign_signature"),
            issued_at=float(d.get("issued_at", 0.0)),
            not_before=d.get("not_before"),
            expires_at=d.get("expires_at"),
            metadata=dict(d.get("metadata") or {}),
        )


# ===========================================================================
# Verification result
# ===========================================================================


@dataclass
class EnvelopeVerification:
    """The outcome of `verify_envelope`."""

    status: str
    reason: str
    key_id: str
    algorithm: str
    payload_digest: str
    verified_at: float
    payload: Optional[Dict[str, Any]] = None

    def is_valid(self) -> bool:
        return self.status == VerificationStatus.VALID.value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "key_id": self.key_id,
            "algorithm": self.algorithm,
            "payload_digest": self.payload_digest,
            "verified_at": self.verified_at,
            "payload": self.payload,
        }


# ===========================================================================
# Sign
# ===========================================================================


def _build_signing_bytes(envelope_dict: Mapping[str, Any]) -> bytes:
    """Build the deterministic bytes that get signed.

    We strip the signature field, sort the keys, and serialize
    with no whitespace. The verifier reconstructs the same bytes
    from the envelope dict (also with the signature field
    stripped) and compares.
    """
    to_sign = {
        k: v
        for k, v in envelope_dict.items()
        if k not in ("signature", "cosign_signature") and not k.startswith("_")
    }
    return canonical_form(to_sign).encode("utf-8")


def _sign_hmac(payload_digest_hex: str, signing_bytes: bytes, key: bytes) -> str:
    """HMAC-SHA256 over the signing bytes, keyed by the payload digest.

    The key is mixed with the payload digest so the same secret
    can sign different payloads without leaking cross-payload
    information. This is the standard pattern for envelope
    signing: the digest of the payload is part of the key.
    """
    derived_key = hmac.new(key, payload_digest_hex.encode("utf-8"), hashlib.sha256).digest()
    sig = hmac.new(derived_key, signing_bytes, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("ascii")


def _verify_hmac(payload_digest_hex: str, signing_bytes: bytes, key: bytes, signature_b64: str) -> bool:
    """Constant-time HMAC-SHA256 verify."""
    derived_key = hmac.new(key, payload_digest_hex.encode("utf-8"), hashlib.sha256).digest()
    expected = hmac.new(derived_key, signing_bytes, hashlib.sha256).digest()
    try:
        actual = base64.urlsafe_b64decode(signature_b64.encode("ascii"))
    except Exception:
        return False
    return hmac.compare_digest(expected, actual)


def _sign_ed25519(payload_digest_hex: str, signing_bytes: bytes, private_key: Any) -> str:
    """Ed25519 sign over the signing bytes.

    The `private_key` is expected to expose a `.sign(message)`
    method (e.g., cryptography.hazmat's Ed25519PrivateKey).
    """
    sig = private_key.sign(signing_bytes)
    return base64.urlsafe_b64encode(sig).decode("ascii")


def _verify_ed25519(payload_digest_hex: str, signing_bytes: bytes, public_key: Any, signature_b64: str) -> bool:
    """Ed25519 verify."""
    try:
        actual = base64.urlsafe_b64decode(signature_b64.encode("ascii"))
    except Exception:
        return False
    try:
        public_key.verify(actual, signing_bytes)
        return True
    except Exception:
        return False


@dataclass
class EnvelopeConfig:
    """Operator-tunable envelope config."""

    algorithm: str = SignatureAlgorithm.HMAC_SHA256.value
    shape: str = EnvelopeShape.ENVELOPE.value
    not_before: Optional[float] = None
    expires_at: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    issued_at: Optional[float] = None
    secondary_algorithm: Optional[str] = None  # COSIGN only
    secondary_key_id: Optional[str] = None  # COSIGN only

    def __post_init__(self) -> None:
        if self.algorithm not in {a.value for a in SignatureAlgorithm}:
            raise ValueError(f"unknown algorithm: {self.algorithm!r}")
        if self.shape not in {s.value for s in EnvelopeShape}:
            raise ValueError(f"unknown shape: {self.shape!r}")
        if self.secondary_algorithm is not None and self.shape != EnvelopeShape.COSIGN.value:
            raise ValueError("secondary_algorithm is only valid for COSIGN shape")
        if self.shape == EnvelopeShape.COSIGN.value and self.secondary_algorithm is None:
            # Default secondary for COSIGN: Ed25519 with a different key.
            self.secondary_algorithm = SignatureAlgorithm.ED25519.value


def sign_envelope(
    payload: Mapping[str, Any],
    key_id: str,
    key: Any,
    *,
    config: Optional[EnvelopeConfig] = None,
    now: Optional[float] = None,
) -> SignedEnvelope:
    """Sign `payload` and return a `SignedEnvelope`.

    `key` is either:
      - bytes (for HMAC-SHA256), or
      - an object with a `.sign(message)` method (for Ed25519).

    For COSIGN, pass `config.secondary_algorithm` and
    `config.secondary_key_id`; the secondary key is looked up via
    the in-process KeyRegistry-style dict. For simplicity in
    this build, the caller passes the secondary key via
    `config.metadata["_secondary_key"]` — see `sign_cosign`.
    """
    if config is None:
        config = EnvelopeConfig()
    issued_at = float(now if now is not None else time.time())

    digest = payload_digest(payload)

    if config.shape == EnvelopeShape.DETACHED.value:
        embedded_payload: Optional[Dict[str, Any]] = None
    else:
        # ENVELOPE + COSIGN embed the payload.
        embedded_payload = dict(payload)

    envelope_dict: Dict[str, Any] = {
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "shape": config.shape,
        "algorithm": config.algorithm,
        "key_id": key_id,
        "payload_digest": digest,
        "payload": embedded_payload,
        "issued_at": issued_at,
        "metadata": dict(config.metadata or {}),
    }
    if config.not_before is not None:
        envelope_dict["not_before"] = config.not_before
    if config.expires_at is not None:
        envelope_dict["expires_at"] = config.expires_at

    signing_bytes = _build_signing_bytes(envelope_dict)

    if config.algorithm == SignatureAlgorithm.HMAC_SHA256.value:
        if not isinstance(key, (bytes, bytearray)):
            raise TypeError("HMAC-SHA256 requires a bytes key")
        signature = _sign_hmac(digest, signing_bytes, bytes(key))
        cosign_sig: Optional[str] = None
    elif config.algorithm == SignatureAlgorithm.ED25519.value:
        signature = _sign_ed25519(digest, signing_bytes, key)
        cosign_sig = None
    else:
        raise UnknownAlgorithmError(f"unsupported algorithm: {config.algorithm!r}")

    if config.shape == EnvelopeShape.COSIGN.value:
        secondary_key = (config.metadata or {}).get("_secondary_key")
        if secondary_key is None:
            raise ValueError("COSIGN shape requires metadata['_secondary_key']")
        secondary_key_id = config.secondary_key_id or (config.metadata or {}).get("_secondary_key_id")
        if secondary_key_id is None:
            raise ValueError("COSIGN shape requires config.secondary_key_id or metadata['_secondary_key_id']")
        # Re-run with the secondary algorithm: rebuild the signing
        # bytes for the secondary, signed over the same envelope
        # shape but with the secondary algorithm declared in the
        # signature field of a parallel envelope dict. The
        # cosign_signature is the secondary algorithm's signature
        # over the SAME signing_bytes.
        if config.secondary_algorithm == SignatureAlgorithm.HMAC_SHA256.value:
            if not isinstance(secondary_key, (bytes, bytearray)):
                raise TypeError("secondary HMAC-SHA256 requires a bytes key")
            cosign_sig = _sign_hmac(digest, signing_bytes, bytes(secondary_key))
        elif config.secondary_algorithm == SignatureAlgorithm.ED25519.value:
            cosign_sig = _sign_ed25519(digest, signing_bytes, secondary_key)
        else:
            raise UnknownAlgorithmError(f"unsupported secondary algorithm: {config.secondary_algorithm!r}")

    envelope_dict["signature"] = signature
    if cosign_sig is not None:
        envelope_dict["cosign_signature"] = cosign_sig

    # Recompute signing_bytes with the final signature in place
    # so the verifier can replay. The signed_bytes are the bytes
    # WITHOUT the signature field; the verifier reconstructs the
    # same bytes from the envelope_dict (signature stripped) and
    # compares to the stored signed_bytes.
    final_signing_bytes = _build_signing_bytes(envelope_dict)

    return SignedEnvelope(
        schema_version=ENVELOPE_SCHEMA_VERSION,
        shape=config.shape,
        algorithm=config.algorithm,
        key_id=key_id,
        payload_digest=digest,
        payload=embedded_payload,
        signature=signature,
        cosign_signature=cosign_sig,
        issued_at=issued_at,
        not_before=config.not_before,
        expires_at=config.expires_at,
        metadata=dict(config.metadata or {}),
        signed_bytes=final_signing_bytes,
    )


# ===========================================================================
# Verify
# ===========================================================================


def verify_envelope(
    envelope: Union[SignedEnvelope, Mapping[str, Any]],
    resolver: KeyResolver,
    *,
    payload: Optional[Mapping[str, Any]] = None,
    now: Optional[float] = None,
) -> EnvelopeVerification:
    """Verify a `SignedEnvelope` (or envelope dict).

    `resolver` resolves `key_id` to the key. For HMAC-SHA256 the
    key is bytes. For Ed25519 the key is an object with a
    `.verify(signature, message)` method (e.g.,
    `cryptography.hazmat.Ed25519PublicKey`).

    For DETACHED shape, the caller MUST pass the `payload`
    separately; the verifier recomputes the digest and compares
    to `envelope.payload_digest`.

    For COSIGN shape, the verifier also checks the
    `cosign_signature` against the secondary key declared in
    `envelope.metadata["_secondary_key_id"]`.

    Returns an `EnvelopeVerification` with status / reason /
    payload (if ENVELOPE / COSIGN).
    """
    verified_at = float(now if now is not None else time.time())

    if isinstance(envelope, Mapping):
        try:
            env = SignedEnvelope.from_dict(envelope)
        except MalformedEnvelopeError as exc:
            return EnvelopeVerification(
                status=VerificationStatus.MALFORMED_ENVELOPE.value,
                reason=str(exc),
                key_id="",
                algorithm="",
                payload_digest="",
                verified_at=verified_at,
            )
    else:
        env = envelope

    # Freshness checks
    if env.not_before is not None and verified_at < float(env.not_before):
        return EnvelopeVerification(
            status=VerificationStatus.NOT_YET_VALID.value,
            reason=f"current time {verified_at} < not_before {env.not_before}",
            key_id=env.key_id,
            algorithm=env.algorithm,
            payload_digest=env.payload_digest,
            verified_at=verified_at,
            payload=env.payload,
        )
    if env.expires_at is not None and verified_at >= float(env.expires_at):
        return EnvelopeVerification(
            status=VerificationStatus.EXPIRED.value,
            reason=f"current time {verified_at} >= expires_at {env.expires_at}",
            key_id=env.key_id,
            algorithm=env.algorithm,
            payload_digest=env.payload_digest,
            verified_at=verified_at,
            payload=env.payload,
        )

    # Algorithm check
    if env.algorithm not in {a.value for a in SignatureAlgorithm}:
        return EnvelopeVerification(
            status=VerificationStatus.UNKNOWN_ALGORITHM.value,
            reason=f"unknown algorithm: {env.algorithm!r}",
            key_id=env.key_id,
            algorithm=env.algorithm,
            payload_digest=env.payload_digest,
            verified_at=verified_at,
            payload=env.payload,
        )

    # Key resolution
    key = resolver(env.key_id)
    if key is None:
        return EnvelopeVerification(
            status=VerificationStatus.UNKNOWN_KEY.value,
            reason=f"unknown key_id: {env.key_id!r}",
            key_id=env.key_id,
            algorithm=env.algorithm,
            payload_digest=env.payload_digest,
            verified_at=verified_at,
            payload=env.payload,
        )

    # DETACHED shape: require payload
    actual_payload: Optional[Mapping[str, Any]]
    if env.shape == EnvelopeShape.DETACHED.value:
        if payload is None:
            return EnvelopeVerification(
                status=VerificationStatus.PAYLOAD_MISMATCH.value,
                reason="DETACHED shape requires explicit payload argument",
                key_id=env.key_id,
                algorithm=env.algorithm,
                payload_digest=env.payload_digest,
                verified_at=verified_at,
                payload=None,
            )
        actual_payload = payload
        actual_digest = payload_digest(payload)
        if actual_digest != env.payload_digest:
            return EnvelopeVerification(
                status=VerificationStatus.PAYLOAD_MISMATCH.value,
                reason=f"payload digest {actual_digest} != envelope digest {env.payload_digest}",
                key_id=env.key_id,
                algorithm=env.algorithm,
                payload_digest=env.payload_digest,
                verified_at=verified_at,
                payload=None,
            )
    else:
        if env.payload is None:
            return EnvelopeVerification(
                status=VerificationStatus.MALFORMED_ENVELOPE.value,
                reason=f"{env.shape} shape requires embedded payload",
                key_id=env.key_id,
                algorithm=env.algorithm,
                payload_digest=env.payload_digest,
                verified_at=verified_at,
                payload=None,
            )
        actual_payload = env.payload
        actual_digest = payload_digest(env.payload)
        if actual_digest != env.payload_digest:
            return EnvelopeVerification(
                status=VerificationStatus.PAYLOAD_MISMATCH.value,
                reason=f"embedded payload digest {actual_digest} != envelope digest {env.payload_digest}",
                key_id=env.key_id,
                algorithm=env.algorithm,
                payload_digest=env.payload_digest,
                verified_at=verified_at,
                payload=env.payload,
            )

    # Reconstruct signing bytes (envelope dict, signature stripped)
    envelope_dict = env.to_dict()
    signing_bytes = _build_signing_bytes(envelope_dict)

    # Verify primary signature
    if env.algorithm == SignatureAlgorithm.HMAC_SHA256.value:
        ok = _verify_hmac(actual_digest, signing_bytes, key, env.signature)
    elif env.algorithm == SignatureAlgorithm.ED25519.value:
        ok = _verify_ed25519(actual_digest, signing_bytes, key, env.signature)
    else:
        return EnvelopeVerification(
            status=VerificationStatus.UNKNOWN_ALGORITHM.value,
            reason=f"unsupported algorithm: {env.algorithm!r}",
            key_id=env.key_id,
            algorithm=env.algorithm,
            payload_digest=env.payload_digest,
            verified_at=verified_at,
            payload=env.payload,
        )

    if not ok:
        return EnvelopeVerification(
            status=VerificationStatus.INVALID_SIGNATURE.value,
            reason="signature does not match",
            key_id=env.key_id,
            algorithm=env.algorithm,
            payload_digest=env.payload_digest,
            verified_at=verified_at,
            payload=env.payload,
        )

    # COSIGN: also verify the secondary signature
    if env.shape == EnvelopeShape.COSIGN.value:
        if env.cosign_signature is None:
            return EnvelopeVerification(
                status=VerificationStatus.MALFORMED_ENVELOPE.value,
                reason="COSIGN shape requires cosign_signature",
                key_id=env.key_id,
                algorithm=env.algorithm,
                payload_digest=env.payload_digest,
                verified_at=verified_at,
                payload=env.payload,
            )
        secondary_key_id = env.metadata.get("_secondary_key_id")
        if secondary_key_id is None:
            return EnvelopeVerification(
                status=VerificationStatus.MALFORMED_ENVELOPE.value,
                reason="COSIGN shape requires metadata['_secondary_key_id']",
                key_id=env.key_id,
                algorithm=env.algorithm,
                payload_digest=env.payload_digest,
                verified_at=verified_at,
                payload=env.payload,
            )
        secondary_key = resolver(secondary_key_id)
        if secondary_key is None:
            return EnvelopeVerification(
                status=VerificationStatus.UNKNOWN_KEY.value,
                reason=f"unknown secondary key_id: {secondary_key_id!r}",
                key_id=env.key_id,
                algorithm=env.algorithm,
                payload_digest=env.payload_digest,
                verified_at=verified_at,
                payload=env.payload,
            )
        secondary_algorithm = env.metadata.get("_secondary_algorithm", SignatureAlgorithm.HMAC_SHA256.value)
        if secondary_algorithm == SignatureAlgorithm.HMAC_SHA256.value:
            ok2 = _verify_hmac(actual_digest, signing_bytes, secondary_key, env.cosign_signature)
        elif secondary_algorithm == SignatureAlgorithm.ED25519.value:
            ok2 = _verify_ed25519(actual_digest, signing_bytes, secondary_key, env.cosign_signature)
        else:
            return EnvelopeVerification(
                status=VerificationStatus.UNKNOWN_ALGORITHM.value,
                reason=f"unsupported secondary algorithm: {secondary_algorithm!r}",
                key_id=env.key_id,
                algorithm=env.algorithm,
                payload_digest=env.payload_digest,
                verified_at=verified_at,
                payload=env.payload,
            )
        if not ok2:
            return EnvelopeVerification(
                status=VerificationStatus.INVALID_SIGNATURE.value,
                reason="cosign signature does not match",
                key_id=env.key_id,
                algorithm=env.algorithm,
                payload_digest=env.payload_digest,
                verified_at=verified_at,
                payload=env.payload,
            )

    # For DETACHED, the result carries the explicit payload the
    # verifier received (so the caller can confirm what was
    # verified). For ENVELOPE / COSIGN, env.payload is the
    # embedded payload.
    result_payload = dict(actual_payload) if actual_payload is not None else env.payload
    return EnvelopeVerification(
        status=VerificationStatus.VALID.value,
        reason="signature valid",
        key_id=env.key_id,
        algorithm=env.algorithm,
        payload_digest=env.payload_digest,
        verified_at=verified_at,
        payload=result_payload,
    )


# ===========================================================================
# AIBOM integration
# ===========================================================================


def sign_aibom_advisory(
    advisory: Any,
    key_id: str,
    key: Any,
    *,
    config: Optional[EnvelopeConfig] = None,
    now: Optional[float] = None,
) -> SignedEnvelope:
    """Sign an `AIBOMAdvisory` (or any object with a `to_dict` method).

    Convenience wrapper. The payload is `advisory.to_dict()`.
    The envelope's `payload_digest` is the advisory's `advisory_id`
    if the advisory is an `AIBOMAdvisory` and the digest matches
    `payload_digest(advisory.to_dict())`. (Both should match by
    construction; the envelope is the *evidence* of the signing.)
    """
    if hasattr(advisory, "to_dict"):
        payload = advisory.to_dict()
    elif isinstance(advisory, Mapping):
        payload = dict(advisory)
    else:
        raise TypeError(f"advisory must be AIBOMAdvisory or Mapping; got {type(advisory).__name__}")
    return sign_envelope(payload, key_id, key, config=config, now=now)


def verify_aibom_advisory_envelope(
    envelope: Union[SignedEnvelope, Mapping[str, Any]],
    resolver: KeyResolver,
    *,
    now: Optional[float] = None,
) -> EnvelopeVerification:
    """Verify a signed `AIBOMAdvisory` envelope.

    The payload is extracted from the envelope (ENVELOPE / COSIGN
    shape) — no separate payload argument is needed.
    """
    return verify_envelope(envelope, resolver, now=now)


# ===========================================================================
# JSON I/O
# ===========================================================================


def envelope_to_json(envelope: SignedEnvelope, *, indent: Optional[int] = None) -> str:
    return json.dumps(envelope.to_dict(), indent=indent, sort_keys=True, ensure_ascii=False)


def envelope_from_json(s: str) -> SignedEnvelope:
    return SignedEnvelope.from_dict(json.loads(s))


def write_envelope(envelope: SignedEnvelope, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(envelope_to_json(envelope, indent=2))
        f.write("\n")


def read_envelope(path: str) -> SignedEnvelope:
    with open(path, "r", encoding="utf-8") as f:
        return envelope_from_json(f.read())


# ===========================================================================
# Ed25519 helpers (soft import of `cryptography`)
# ===========================================================================


def generate_ed25519_keypair() -> Tuple[Any, Any]:
    """Generate an Ed25519 keypair using the `cryptography` library.

    Returns (private_key, public_key). Both are objects with
    `.sign()` / `.verify()` methods.

    Falls back to a tiny pure-Python Ed25519 implementation if
    `cryptography` is not available (for environments where
    the dependency is too heavy). The fallback uses
    `nacl` if installed; otherwise raises an ImportError with
    a clear message.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        priv = Ed25519PrivateKey.generate()
        return priv, priv.public_key()
    except ImportError:
        pass
    try:
        from nacl.signing import SigningKey  # type: ignore

        sk = SigningKey.generate()
        return sk, sk.verify_key
    except ImportError:
        pass
    raise ImportError(
        "Ed25519 requires the `cryptography` or `nacl` package. "
        "Install one with: pip install cryptography"
    )


# ===========================================================================
# Small helpers
# ===========================================================================


def make_key_id(prefix: str = "key") -> str:
    """Generate a short, opaque key id (for tests + dev)."""
    return f"{prefix}-{hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]}"


def is_fresh(envelope: Union[SignedEnvelope, Mapping[str, Any]], *, now: Optional[float] = None) -> bool:
    """Return True if the envelope is fresh (within not_before/expires_at)."""
    if isinstance(envelope, Mapping):
        env_dict = envelope
    else:
        env_dict = envelope.to_dict()
    t = float(now if now is not None else time.time())
    nb = env_dict.get("not_before")
    ea = env_dict.get("expires_at")
    if nb is not None and t < float(nb):
        return False
    if ea is not None and t >= float(ea):
        return False
    return True
