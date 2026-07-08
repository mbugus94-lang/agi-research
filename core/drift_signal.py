"""Drift signal — a PagerDuty-style AIOps primitive for signed advisories.

Closes the 2026-07-08 build's next-priority item:
  "Wire `envelope.timestamp` into a PagerDuty-style drift signal —
   `cli/drift_signal.py` reads a directory of envelopes and emits a
   CSV of `(envelope_id, key_id, age_seconds, status)` for AIOps
   ingestion. The envelope is the substrate; the drift signal is the
   AIOps primitive."

Why this exists
---------------
A signed envelope tells you two things about an advisory:

  1. *Is the advisory authentic?* (signature valid, key known, payload
     digest matches, freshness window respected.)
  2. *Is the advisory still relevant?* (issued_at is recent; not
     expired; key still trusted; no chain-of-custody gaps.)

Traditional PagerDuty AIOps tracks software crashes. Agent
infrastructure drift is different: an agent can be *silent* while
fabricating plausible external obstacles (Constraint-Evasive
Fabrication, CEF) or while still emitting valid signatures against
a key that has since been revoked. The drift signal is the primitive
that catches the second class:

  - "this envelope is valid but 4 hours old — it predates the
    key rotation at 14:00, so it must be re-issued"
  - "this envelope is valid but the signing key is in the
    drift-detection set — possible model-replay attack"
  - "this envelope is from a *new* key we have never seen
    before — first-encounter event, low confidence"
  - "this envelope is from a *frequent* key (normal operation)"

The drift signal is *measurement only*. It does not page anyone, it
does not rotate keys, it does not quarantine envelopes. It produces
a CSV of one row per envelope plus a JSON summary, so downstream
AIOps (PagerDuty, Opsgenie, Datadog, custom alertmanager) can
decide what to do.

Conservative posture
--------------------
- The signal is a pure function of (envelope_path, key_resolver, now).
  No I/O side effects beyond reading files + writing the report.
- Drift flags are *named* and *explicit*. There is no implicit
  "drift score" — each flag is a boolean an operator can act on.
- A malformed envelope produces a `MALFORMED` row, not an exception.
  The CLI never crashes on a single bad file.
- A missing key in the registry produces an `UNKNOWN_KEY` row, not
  a hard fail. The signal records the gap, doesn't refuse to
  produce output.
- All time comparisons are conservative: an envelope is "fresh" iff
  `now ∈ [not_before, expires_at]`. Outside that window, the signal
  flags `EXPIRED` or `NOT_YET_VALID`. There is no "soft" expiry.
- The CLI never invokes keys for signing. It only *verifies*
  (using the operator-supplied keys/secrets) and *classifies*. The
  substrate is read-only.
- The drift signal does not modify the envelope, the keys, or the
  filesystem beyond writing the report.

Research motivation (2026-07-08)
---------------------------------
- *PagerDuty AIOps for agents (Forbes, 2026-07-02)*: "agent and
  model drift show up differently than a conventional software
  crash". The drift signal is the *signal* the AIOps would alert
  on. An unsigned or unverified advisory IS the drift signal.
- *Agent Gateways (Forbes, Nutanix, Arcade, HashiCorp Terraform
  MCP, 2026-07)*: every tool call passes through a control plane
  emitting signed advisories. The drift signal is the AIOps layer
  *above* the control plane.
- *ToolBench-X (arXiv:2606.25819)*: 5 hazard types for tool
  unreliability (Spec Drift, Invocation Error, Execution Failure,
  Output Drift, Cross-source Conflict). The drift signal's flags
  *name* what the benchmark is trying to detect — `STALE` is
  output drift, `FIRST_ENCOUNTER_KEY` is invocation drift,
  `EXPIRED` is execution drift.
- *arXiv:2606.26027 (Multi-step RL collapse)*: RL tool-use
  collapse is from control-token probability spikes, not lost
  capability. The drift signal's `STALE` flag catches the
  model-replay case where the agent is emitting *valid* but
  *stale* advice.
- *Vinton Cerf (Open Frontier, 2026-06-30)*: "the rise of
  multi-source agents will force the industry back toward formal,
  standardized protocols — the way TCP/IP did for the early
  internet." The drift signal is a TCP-style primitive:
  envelopes are packets, the signal is a sequence-number /
  timestamp check, the AIOps is the receiver.

Wire format
-----------
CSV header (fixed, in this order):

    envelope_id,key_id,algorithm,shape,issued_at,age_seconds,
    not_before,expires_at,status,drift_flags,reasons,payload_digest

JSON summary:

    {
      "directory": "...",
      "generated_at": 1700000000.0,
      "n_envelopes": N,
      "n_valid": V,
      "n_invalid": I,
      "n_malformed": M,
      "drift_counts": {"STALE": ..., "EXPIRED": ..., ...},
      "first_encounter_keys": [...],
      "frequent_keys": [...],
      "envelopes": [ <one CSV row's dict> , ... ]
    }

Drift flags (string set; an envelope can have multiple)
-------------------------------------------------------
* `STALE`            — age > stale_threshold_seconds (default 3600)
* `EXPIRED`          — `now > expires_at` (envelope past its window)
* `NOT_YET_VALID`    — `now < not_before` (clock skew or future-dated)
* `UNKNOWN_KEY`      — `key_id` not in the resolver (provenance gap)
* `INVALID_SIGNATURE`— signature did not verify
* `PAYLOAD_MISMATCH` — digest mismatch (tamper)
* `MALFORMED`        — file is not a parseable envelope
* `FIRST_ENCOUNTER`  — first time this `key_id` was seen in the
                        directory (low-confidence, normally informational)
* `OLD_ALGORITHM`    — algorithm is not in the trusted set (default:
                        {hmac-sha256, ed25519})

Status values
-------------
* `VALID`       — signature valid, fresh, key known, no drift
* `DRIFT`       — signature valid, fresh, key known, but at least
                   one drift flag set (e.g. STALE, FIRST_ENCOUNTER)
* `INVALID`     — signature invalid OR payload mismatch OR unknown key
                   (whichever fires first)
* `EXPIRED`     — not_before / expires_at window violated (but signature
                   may still be valid; the drift signal still flags
                   it because the consumer should refuse to act)
* `NOT_YET_VALID`— same as EXPIRED but for the future-side window
* `MALFORMED`   — file is not a parseable envelope
"""

from __future__ import annotations

import csv
import io
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

# Ensure repo root on sys.path for `core.*` imports when used as a script
import sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.signed_advisory_envelope import (  # noqa: E402
    KeyRegistry,
    SignedEnvelope,
    VerificationStatus,
    envelope_from_json,
    is_fresh,
    read_envelope,
    verify_envelope,
)


# ===========================================================================
# Constants
# ===========================================================================


CSV_HEADER: Tuple[str, ...] = (
    "envelope_id",
    "key_id",
    "algorithm",
    "shape",
    "issued_at",
    "age_seconds",
    "not_before",
    "expires_at",
    "status",
    "drift_flags",
    "reasons",
    "payload_digest",
)

# Drift-flag constants (string literals; also used as enum-ish values)
DRIFT_STALE = "STALE"
DRIFT_EXPIRED = "EXPIRED"
DRIFT_NOT_YET_VALID = "NOT_YET_VALID"
DRIFT_UNKNOWN_KEY = "UNKNOWN_KEY"
DRIFT_INVALID_SIGNATURE = "INVALID_SIGNATURE"
DRIFT_PAYLOAD_MISMATCH = "PAYLOAD_MISMATCH"
DRIFT_MALFORMED = "MALFORMED"
DRIFT_FIRST_ENCOUNTER = "FIRST_ENCOUNTER"
DRIFT_OLD_ALGORITHM = "OLD_ALGORITHM"

# Drift flags that are *informational* — they don't change the
# status from VALID to DRIFT, they just annotate.
_INFORMATIONAL_FLAGS: frozenset = frozenset({DRIFT_FIRST_ENCOUNTER})

# Drift flags that always imply INVALID (i.e. signature / key / payload
# did not check out). Even if the envelope is fresh, the consumer
# should refuse to act.
_INVALIDATING_FLAGS: frozenset = frozenset({
    DRIFT_INVALID_SIGNATURE,
    DRIFT_PAYLOAD_MISMATCH,
    DRIFT_UNKNOWN_KEY,
    DRIFT_MALFORMED,
    DRIFT_OLD_ALGORITHM,
})

# Drift flags that imply EXPIRED / NOT_YET_VALID (the consumer should
# refuse because the freshness window is violated, but the
# signature may still be valid).
_FRESHNESS_FLAGS: frozenset = frozenset({DRIFT_EXPIRED, DRIFT_NOT_YET_VALID})

DEFAULT_STALE_THRESHOLD_SECONDS: float = 3600.0  # 1 hour

DEFAULT_TRUSTED_ALGORITHMS: frozenset = frozenset({"hmac-sha256", "ed25519"})


# ===========================================================================
# Configuration
# ===========================================================================


@dataclass
class DriftConfig:
    """Operator-tunable drift-signal configuration.

    Attributes:
      stale_threshold_seconds: envelopes older than this age get the
        STALE flag. Default 3600 (1 hour).
      trusted_algorithms: set of algorithm names that are considered
        current. An envelope with an algorithm outside this set gets
        OLD_ALGORITHM. Default {hmac-sha256, ed25519}.
      include_files: optional explicit list of envelope file paths.
        If None, the directory is scanned for `*.json` files.
      follow_symlinks: whether to follow symlinks when scanning the
        directory. Default False (safer).
      now: optional override for the current time. Tests pass a fixed
        value; production leaves it None (uses time.time()).
    """

    stale_threshold_seconds: float = DEFAULT_STALE_THRESHOLD_SECONDS
    trusted_algorithms: frozenset = field(default_factory=lambda: DEFAULT_TRUSTED_ALGORITHMS)
    include_files: Optional[Tuple[str, ...]] = None
    follow_symlinks: bool = False
    now: Optional[float] = None


# ===========================================================================
# Result types
# ===========================================================================


@dataclass
class DriftRow:
    """A single row of the drift signal.

    One row per envelope file in the scanned directory (or in the
    explicit `include_files` list). The row is the substrate for
    both the CSV output and the JSON summary.
    """

    envelope_id: str
    key_id: str
    algorithm: str
    shape: str
    issued_at: float
    age_seconds: float
    not_before: Optional[float]
    expires_at: Optional[float]
    status: str
    drift_flags: List[str]
    reasons: List[str]
    payload_digest: str

    def to_csv_dict(self) -> Dict[str, str]:
        """Render the row as a flat dict for csv.DictWriter."""
        return {
            "envelope_id": self.envelope_id,
            "key_id": self.key_id,
            "algorithm": self.algorithm,
            "shape": self.shape,
            "issued_at": f"{self.issued_at:.6f}",
            "age_seconds": f"{self.age_seconds:.6f}",
            "not_before": "" if self.not_before is None else f"{self.not_before:.6f}",
            "expires_at": "" if self.expires_at is None else f"{self.expires_at:.6f}",
            "status": self.status,
            "drift_flags": ",".join(self.drift_flags),
            "reasons": "|".join(self.reasons),
            "payload_digest": self.payload_digest,
        }


@dataclass
class DriftReport:
    """The full drift signal for a directory of envelopes.

    The report is the unit of output. It is deterministic given the
    same (directory, registry, now) inputs.
    """

    directory: str
    generated_at: float
    n_envelopes: int
    n_valid: int
    n_drift: int
    n_invalid: int
    n_expired: int
    n_not_yet_valid: int
    n_malformed: int
    drift_counts: Dict[str, int]
    first_encounter_keys: List[str]
    frequent_keys: List[str]
    rows: List[DriftRow]

    def to_csv(self) -> str:
        """Render the report as a CSV string.

        The CSV is the AIOps ingestion format — one row per envelope,
        fixed column order (CSV_HEADER), no quoting of numeric fields.
        """
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(CSV_HEADER), quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for row in self.rows:
            writer.writerow(row.to_csv_dict())
        return buf.getvalue()

    def to_dict(self) -> Dict[str, Any]:
        """Render the report as a JSON-friendly dict."""
        return {
            "directory": self.directory,
            "generated_at": self.generated_at,
            "n_envelopes": self.n_envelopes,
            "n_valid": self.n_valid,
            "n_drift": self.n_drift,
            "n_invalid": self.n_invalid,
            "n_expired": self.n_expired,
            "n_not_yet_valid": self.n_not_yet_valid,
            "n_malformed": self.n_malformed,
            "drift_counts": dict(self.drift_counts),
            "first_encounter_keys": list(self.first_encounter_keys),
            "frequent_keys": list(self.frequent_keys),
            "envelopes": [row.to_csv_dict() for row in self.rows],
        }


# ===========================================================================
# Core: classify one envelope
# ===========================================================================


def _envelope_id(env: SignedEnvelope) -> str:
    """A stable identifier for an envelope (sha256 of its canonical form)."""
    import hashlib
    canonical = json.dumps(env.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _classify_one(
    env: SignedEnvelope,
    *,
    registry: KeyRegistry,
    config: DriftConfig,
    now: float,
) -> DriftRow:
    """Classify a single envelope and produce a DriftRow.

    The classification is conservative:
      - Drift flags are *named* and explicit.
      - An envelope with no flags is `VALID`.
      - An envelope with freshness flags is `EXPIRED` / `NOT_YET_VALID`.
      - An envelope with invalidating flags is `INVALID`.
      - An envelope with only informational flags is `DRIFT`
        (e.g. FIRST_ENCOUNTER, STALE).
    """
    flags: List[str] = []
    reasons: List[str] = []

    # --- algorithm check ---
    if env.algorithm not in config.trusted_algorithms:
        flags.append(DRIFT_OLD_ALGORITHM)
        reasons.append(f"algorithm '{env.algorithm}' is not in trusted set")

    # --- freshness check (use the substrate's is_fresh helper) ---
    fresh = is_fresh(env, now=now)
    if not fresh:
        if env.expires_at is not None and now > env.expires_at:
            flags.append(DRIFT_EXPIRED)
            reasons.append(
                f"now ({now:.3f}) > expires_at ({env.expires_at:.3f})"
            )
        if env.not_before is not None and now < env.not_before:
            flags.append(DRIFT_NOT_YET_VALID)
            reasons.append(
                f"now ({now:.3f}) < not_before ({env.not_before:.3f})"
            )

    # --- signature / key check ---
    resolver = registry.resolve
    verification = verify_envelope(env, resolver, now=now)
    if verification.status == VerificationStatus.VALID.value:
        pass
    elif verification.status == VerificationStatus.UNKNOWN_KEY.value:
        flags.append(DRIFT_UNKNOWN_KEY)
        reasons.append(
            f"key_id '{env.key_id}' not in registry (resolver returned {verification.reason})"
        )
    elif verification.status == VerificationStatus.PAYLOAD_MISMATCH.value:
        flags.append(DRIFT_PAYLOAD_MISMATCH)
        reasons.append(f"payload_digest mismatch ({verification.reason})")
    elif verification.status in (
        VerificationStatus.INVALID_SIGNATURE.value,
        VerificationStatus.UNKNOWN_ALGORITHM.value,
    ):
        flags.append(DRIFT_INVALID_SIGNATURE)
        reasons.append(
            f"signature / algorithm verification failed ({verification.reason})"
        )
    elif verification.status == VerificationStatus.EXPIRED.value:
        # verify_envelope re-runs freshness; if it disagrees with
        # is_fresh (e.g. boundary), we still record the EXPIRED flag.
        # Don't double-add; is_fresh above already added it.
        pass
    elif verification.status == VerificationStatus.NOT_YET_VALID.value:
        pass
    else:
        flags.append(DRIFT_INVALID_SIGNATURE)
        reasons.append(f"unexpected verification status: {verification.status}")

    # --- age / staleness check ---
    age = max(0.0, now - float(env.issued_at)) if env.issued_at else 0.0
    if age > config.stale_threshold_seconds:
        flags.append(DRIFT_STALE)
        reasons.append(
            f"age ({age:.1f}s) > stale_threshold ({config.stale_threshold_seconds:.1f}s)"
        )

    # --- derive status ---
    if any(f in _INVALIDATING_FLAGS for f in flags):
        status = "INVALID"
    elif DRIFT_EXPIRED in flags:
        status = "EXPIRED"
    elif DRIFT_NOT_YET_VALID in flags:
        status = "NOT_YET_VALID"
    elif any(f not in _INFORMATIONAL_FLAGS for f in flags):
        status = "DRIFT"
    else:
        status = "VALID"

    return DriftRow(
        envelope_id=_envelope_id(env),
        key_id=str(env.key_id),
        algorithm=str(env.algorithm),
        shape=str(env.shape),
        issued_at=float(env.issued_at),
        age_seconds=float(age),
        not_before=env.not_before,
        expires_at=env.expires_at,
        status=status,
        drift_flags=flags,
        reasons=reasons,
        payload_digest=str(env.payload_digest),
    )


def _classify_malformed(path: str, err: Exception, *, now: float) -> DriftRow:
    """Produce a MALFORMED row when an envelope file cannot be parsed.

    Conservative: the row carries the file path's basename as the
    envelope_id, the error message in `reasons`, and MALFORMED in
    drift_flags. The consumer can grep for MALFORMED to find the
    bad files.
    """
    import hashlib
    base = os.path.basename(path)
    return DriftRow(
        envelope_id=hashlib.sha256(base.encode("utf-8")).hexdigest()[:16],
        key_id="",
        algorithm="",
        shape="",
        issued_at=0.0,
        age_seconds=0.0,
        not_before=None,
        expires_at=None,
        status="MALFORMED",
        drift_flags=[DRIFT_MALFORMED],
        reasons=[f"could not parse envelope: {type(err).__name__}: {err}"],
        payload_digest="",
    )


# ===========================================================================
# Core: scan a directory
# ===========================================================================


def _resolve_paths(directory: str, config: DriftConfig) -> List[str]:
    """Return the list of envelope JSON files to scan.

    If `config.include_files` is set, use it directly (paths are
    relative to the directory or absolute). Otherwise, scan the
    directory for `*.json` files.
    """
    if config.include_files is not None:
        return [str(p) for p in config.include_files]
    paths: List[str] = []
    for entry in sorted(os.listdir(directory)):
        if not entry.endswith(".json"):
            continue
        full = os.path.join(directory, entry)
        if os.path.isdir(full):
            continue
        if not config.follow_symlinks and os.path.islink(full):
            continue
        paths.append(full)
    return paths


def _envelope_paths(directory: str, config: DriftConfig) -> List[str]:
    """Resolve and return envelope file paths to scan."""
    return _resolve_paths(directory, config)


def _classify_directory(
    directory: str,
    registry: KeyRegistry,
    config: DriftConfig,
) -> List[DriftRow]:
    """Scan the directory and produce a list of DriftRows."""
    now = config.now if config.now is not None else time.time()
    paths = _envelope_paths(directory, config)
    rows: List[DriftRow] = []
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
            env = envelope_from_json(raw)
        except Exception as e:  # noqa: BLE001 — surface any parse error
            rows.append(_classify_malformed(path, e, now=now))
            continue
        rows.append(_classify_one(env, registry=registry, config=config, now=now))
    return rows


def _build_report(
    directory: str,
    rows: Sequence[DriftRow],
    *,
    now: float,
) -> DriftReport:
    """Aggregate a list of DriftRows into a DriftReport.

    Deterministic: rows are sorted by envelope_id before aggregation
    so the report is reproducible across runs.
    """
    sorted_rows = sorted(rows, key=lambda r: r.envelope_id)

    drift_counts: Dict[str, int] = {}
    for r in sorted_rows:
        for f in r.drift_flags:
            drift_counts[f] = drift_counts.get(f, 0) + 1

    # First-encounter key tracking: a key that appears exactly once
    # in the directory is treated as a first-encounter event. A key
    # that appears 2+ times is treated as frequent. The per-row
    # FIRST_ENCOUNTER flag is added (idempotently) to each row of a
    # singleton-key directory scan, so the flag is visible in the
    # CSV without the consumer having to look up `first_encounter_keys`.
    key_counts: Dict[str, int] = {}
    for r in sorted_rows:
        if r.key_id:
            key_counts[r.key_id] = key_counts.get(r.key_id, 0) + 1
    first_encounter_keys_set: Set[str] = {
        r.key_id for r in sorted_rows if r.key_id and key_counts[r.key_id] == 1
    }
    frequent_keys_set: Set[str] = {
        r.key_id for r in sorted_rows if r.key_id and key_counts[r.key_id] >= 2
    }
    # Annotate rows whose key is a first-encounter singleton. We rebuild
    # a tuple since DriftRow is a frozen-style dataclass; we use object.__setattr__
    # to bypass the frozen check if any.
    annotated_rows = []
    for r in sorted_rows:
        if r.key_id and r.key_id in first_encounter_keys_set:
            if DRIFT_FIRST_ENCOUNTER not in r.drift_flags:
                new_flags = list(r.drift_flags) + [DRIFT_FIRST_ENCOUNTER]
                try:
                    r.drift_flags = new_flags  # type: ignore[misc]
                except Exception:
                    pass
        annotated_rows.append(r)
    sorted_rows = annotated_rows

    return DriftReport(
        directory=directory,
        generated_at=now,
        n_envelopes=len(sorted_rows),
        n_valid=sum(1 for r in sorted_rows if r.status == "VALID"),
        n_drift=sum(1 for r in sorted_rows if r.status == "DRIFT"),
        n_invalid=sum(1 for r in sorted_rows if r.status == "INVALID"),
        n_expired=sum(1 for r in sorted_rows if r.status == "EXPIRED"),
        n_not_yet_valid=sum(1 for r in sorted_rows if r.status == "NOT_YET_VALID"),
        n_malformed=sum(1 for r in sorted_rows if r.status == "MALFORMED"),
        drift_counts=drift_counts,
        first_encounter_keys=sorted(first_encounter_keys_set),
        frequent_keys=sorted(frequent_keys_set),
        rows=list(sorted_rows),
    )


# ===========================================================================
# Public API
# ===========================================================================


def scan_drift_signal(
    directory: str,
    *,
    registry: KeyRegistry,
    config: Optional[DriftConfig] = None,
) -> DriftReport:
    """Scan a directory of signed envelopes and produce a DriftReport.

    This is the smallest viable install for the drift signal. Pass a
    `KeyRegistry` (already populated with the operator's keys), a
    `DriftConfig` (or None for defaults), and a directory of signed
    envelopes (one JSON file per envelope). The function returns a
    `DriftReport` with the CSV rows and summary counts.

    The function is a pure function of (directory, registry, config).
    No I/O side effects beyond reading the directory and returning
    the report object.
    """
    if config is None:
        config = DriftConfig()
    now = config.now if config.now is not None else time.time()
    rows = _classify_directory(directory, registry, config)
    return _build_report(directory, rows, now=now)


def scan_drift_signal_from_paths(
    paths: Sequence[str],
    *,
    registry: KeyRegistry,
    config: Optional[DriftConfig] = None,
) -> DriftReport:
    """Scan a list of envelope file paths (bypassing directory scan).

    Same as `scan_drift_signal` but takes an explicit list of paths
    rather than a directory. Useful for tests and for AIOps pipelines
    that already have a curated list of envelope files.
    """
    if config is None:
        config = DriftConfig()
    config = DriftConfig(
        stale_threshold_seconds=config.stale_threshold_seconds,
        trusted_algorithms=config.trusted_algorithms,
        include_files=tuple(paths),
        follow_symlinks=config.follow_symlinks,
        now=config.now,
    )
    return scan_drift_signal(
        directory=os.path.commonpath(paths) if len(paths) > 1 else os.path.dirname(paths[0]) or ".",
        registry=registry,
        config=config,
    )


def write_drift_report(
    report: DriftReport,
    *,
    csv_path: Optional[str] = None,
    json_path: Optional[str] = None,
) -> None:
    """Write a DriftReport to disk.

    `csv_path`: write the CSV rows. None = skip.
    `json_path`: write the JSON summary. None = skip.
    The function is conservative: it does not overwrite existing
    files unless they were produced by a previous run (we always
    overwrite — this is a measurement tool, not a stateful one).
    """
    if csv_path:
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            f.write(report.to_csv())
    if json_path:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, sort_keys=True)
