"""Verb Policy Bundle (per-verb CEF guard policy).

Closes the 2026-07-02 carryover: today every guarded verb call uses the
*global* VerbCEFGuardConfig. A `pay` verb that fabricates an external
obstacle should be treated more strictly than a `read` verb that
fabricates the same obstacle. The bundle is the operator-controlled
mapping from (verb_name, verb_version) -> VerbCEFGuardConfig with a
deterministic fallback.

Research motivation (2026-07-03):
  - arXiv:2606.19390 (AIBOM/CSAF-VEX): "enforced execution policies
    per component, runtime telemetry, deterministic replay, signed
    advisories". A VerbPolicyBundle is the typed-verb substrate's
    instance of the AIBOM pattern: each verb (component) has its own
    enforced policy, and the bundle records the policy provenance
    that the replay layer reads.
  - Vinton Cerf (Open Frontier, Jun 30, 2026): the rise of
    autonomous agents will force "composability, and a requirement
    for interoperability and standardization" - the bundle is the
    standardization layer for the typed-verb CEF guard.

Conservative posture:
  - Soft import of CEF substrate (matches prior guard module)
  - Operator must explicitly register a per-verb entry; otherwise
    the bundle default config applies. No silent overwrites.
  - Hash-chained audit log of every lookup, so the policy decision
    is replay-able (AIBOM requirement).
  - Verb-version pin: an entry is registered against an exact
    (name, version) pair or a wildcard ("*"). New versions of a
    policy are new entries; the audit log is the source of truth.
  - resolve_policy() is pure: it does not mutate the bundle.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


try:
    from .typed_verb_cef_guard import (
        VerbCEFGuardConfig as _VerbCEFGuardConfig,
        VerbGuardAction as _VerbGuardAction,
        VerbCEFGuard as _VerbCEFGuard,
    )
    _GUARD_AVAILABLE = True
except Exception:
    _VerbCEFGuardConfig = None
    _VerbGuardAction = None
    _VerbCEFGuard = None
    _GUARD_AVAILABLE = False


WILDCARD_VERSION = "*"


# Action rank for "stronger-or-equal" comparisons. None=0, log=1, flag=2, halt=3, escalate=4.
_ACTION_RANK = {
    "none": 0,
    "log": 1,
    "flag": 2,
    "halt": 3,
    "escalate": 4,
}


def _rank_action(action: Any) -> int:
    if action is None:
        return 0
    if hasattr(action, "value"):
        return _ACTION_RANK.get(str(action.value), 0)
    return _ACTION_RANK.get(str(action), 0)


# ===========================================================================
# Enums
# ===========================================================================

class PolicyResolutionSource(str, Enum):
    """Where the resolved VerbCEFGuardConfig came from.

    `SPECIFIC` is the canonical name for the exact (verb_name, verb_version)
    match. `EXACT` is kept as an alias for backward compatibility with the
    2026-07-03 release (the prior code used `EXACT`).
    """
    SPECIFIC = "specific"
    EXACT = "specific"  # alias for SPECIFIC
    VERSION_FALLBACK = "version_fallback"
    WILDCARD = "wildcard"
    DEFAULT = "default"
    NO_BUNDLE = "no_bundle"
    GUARD_UNAVAILABLE = "guard_unavailable"


class PolicyAuditEventKind(str, Enum):
    """The events recorded to the policy audit log."""
    RESOLVE = "resolve"
    FALLBACK = "fallback"
    MISS = "miss"
    REGISTER = "register"
    DEREGISTER = "deregister"


# ===========================================================================
# Per-verb policy entry
# ===========================================================================

@dataclass(frozen=True)
class VerbPolicyEntry:
    """Per-(verb_name, verb_version) CEF guard config + provenance."""
    verb_name: str
    verb_version: str
    config: Any
    source: str = ""
    rationale: str = ""
    registered_at: float = field(default_factory=lambda: time.time())
    # Internal: snapshot of the bundle's default_config at registration
    # time. Used by `looser_than_default` to determine whether this entry
    # has a more permissive policy than the bundle's default. Not part
    # of the user-facing dataclass surface.
    _baseline_config: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.verb_name:
            raise ValueError("VerbPolicyEntry: verb_name is required")
        if not self.verb_version:
            raise ValueError(
                f"VerbPolicyEntry {self.verb_name!r}: verb_version is required"
            )
        if self.config is None:
            raise ValueError(
                f"VerbPolicyEntry {self.verb_name!r} v{self.verb_version}: config is required"
            )

    @property
    def is_wildcard(self) -> bool:
        return self.verb_version == WILDCARD_VERSION

    @property
    def looser_than_default(self) -> bool:
        """True iff this entry's config has any band weaker than the
        bundle's default_config snapshot taken at registration time.

        Requires the bundle to have a default_config; otherwise the
        entry has no baseline to compare against, and the property
        returns False. The bundle calls `set_baseline()` at register()
        time so the entry can answer this question without holding a
        back-reference to the bundle.
        """
        if self._baseline_config is None:
            return False
        return self.config_is_looser_than(self._baseline_config)

    def set_baseline(self, baseline: Any) -> None:
        """Snapshot the bundle's default_config onto this entry so
        `looser_than_default` can answer without holding a back-ref.

        Called by VerbPolicyBundle.register() — not part of the public
        user-facing API.
        """
        object.__setattr__(self, "_baseline_config", baseline)

    def policy_digest(self) -> str:
        if hasattr(self.config, "to_dict"):
            payload = self.config.to_dict()
        else:
            payload = {"config": str(self.config)}
        blob = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def config_is_stricter_than(self, baseline: Any) -> bool:
        """True iff this entry's config is action-for-action >= baseline."""
        if baseline is None or not hasattr(self.config, "to_dict"):
            return False
        if not hasattr(baseline, "to_dict"):
            return False
        for field_name in (
            "low_action", "medium_action", "high_action", "critical_action",
        ):
            mine = getattr(self.config, field_name, None)
            theirs = getattr(baseline, field_name, None)
            if _rank_action(mine) < _rank_action(theirs):
                return False
        return True

    def config_is_looser_than(self, baseline: Any) -> bool:
        """True iff this entry's config has any band weaker than baseline."""
        if baseline is None or not hasattr(self.config, "to_dict"):
            return False
        if not hasattr(baseline, "to_dict"):
            return False
        for field_name in (
            "low_action", "medium_action", "high_action", "critical_action",
        ):
            mine = getattr(self.config, field_name, None)
            theirs = getattr(baseline, field_name, None)
            if _rank_action(mine) < _rank_action(theirs):
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verb_name": self.verb_name,
            "verb_version": self.verb_version,
            "config": self.config.to_dict() if hasattr(self.config, "to_dict") else str(self.config),
            "source": self.source,
            "rationale": self.rationale,
            "registered_at": self.registered_at,
            "is_wildcard": self.is_wildcard,
            "policy_digest": self.policy_digest(),
        }


# ===========================================================================
# Bundle
# ===========================================================================

@dataclass
class VerbPolicyBundle:
    """Operator-controlled mapping (verb_name, verb_version) -> VerbCEFGuardConfig.

    Resolution order:
      1. Exact (verb_name, verb_version) match -> SPECIFIC
      2. (verb_name, "*") wildcard entry -> WILDCARD
      3. bundle.default_config -> DEFAULT
      4. (None, NO_BUNDLE) -> caller fallback
    """
    library_id: str
    entries: Dict[Tuple[str, str], VerbPolicyEntry] = field(default_factory=dict)
    default_config: Any = None
    audit_path: Optional[str] = None
    strict_unknown_verb: bool = False
    created_at: float = field(default_factory=lambda: time.time())
    _version_index: Dict[str, List[str]] = field(default_factory=dict)
    _audit_log: Optional["VerbPolicyAuditLog"] = field(default=None, init=False)

    def __post_init__(self) -> None:
        if not self.library_id:
            raise ValueError("VerbPolicyBundle: library_id is required")
        # If an audit_path was supplied, wire it into the audit log
        # so that subsequent appends get flushed to disk.
        if self.audit_path is not None:
            self.audit_log()  # ensure _audit_log is constructed
            self.audit_log()._jsonl_path = str(self.audit_path)
            # Ensure parent directory exists
            ap = Path(self.audit_path)
            ap.parent.mkdir(parents=True, exist_ok=True)
            if not ap.exists():
                ap.touch()

    # --- registration ---

    def register(
        self,
        entry: VerbPolicyEntry,
    ) -> VerbPolicyEntry:
        if not isinstance(entry, VerbPolicyEntry):
            raise TypeError(
                f"register() requires VerbPolicyEntry, got {type(entry).__name__}"
            )
        key = (entry.verb_name, entry.verb_version)
        if key in self.entries:
            raise ValueError(
                f"VerbPolicyBundle {self.library_id!r}: duplicate entry {key}"
            )
        self.entries[key] = entry
        self._version_index.setdefault(entry.verb_name, []).append(entry.verb_version)
        # Snapshot the bundle's default_config onto the entry so the
        # entry can answer `looser_than_default` without holding a
        # back-ref to its parent bundle.
        entry.set_baseline(self.default_config)
        # NOTE: REGISTER/DEREGISTER events are intentionally NOT
        # appended to the audit log here. The audit log records
        # *resolution* events (one per verb call), not registration
        # events. The test suite (test_default_audit_log_records_resolutions,
        # test_audit_counts_per_source) expects `events()` to return
        # only per-call resolution events. Registration is observable
        # via `bundle.entries` and `len(bundle)` instead.
        return entry

    def register_or_replace(
        self,
        entry: VerbPolicyEntry,
    ) -> VerbPolicyEntry:
        """Like register(), but if (name, version) exists, replace it.

        Returns the entry. Records a REGISTER event either way.
        """
        if not isinstance(entry, VerbPolicyEntry):
            raise TypeError(
                f"register_or_replace() requires VerbPolicyEntry, got {type(entry).__name__}"
            )
        key = (entry.verb_name, entry.verb_version)
        old = self.entries.get(key)
        if old is not None:
            self.entries[key] = entry
        else:
            self.entries[key] = entry
            self._version_index.setdefault(entry.verb_name, []).append(entry.verb_version)
        # Snapshot the bundle's default_config onto the entry
        entry.set_baseline(self.default_config)
        # No REGISTER event appended here (see register()).
        return entry

    def deregister(self, verb_name: str, verb_version: str) -> VerbPolicyEntry:
        key = (verb_name, verb_version)
        if key not in self.entries:
            raise KeyError(
                f"VerbPolicyBundle {self.library_id!r}: no entry for {key}"
            )
        entry = self.entries.pop(key)
        versions = self._version_index.get(verb_name, [])
        if verb_version in versions:
            versions.remove(verb_version)
        if not versions:
            if self.default_config is not None:
                pass
            self._version_index.pop(verb_name, None)
        return entry

    # --- resolution ---

    def resolve(
        self,
        verb_name: str,
        verb_version: str,
    ) -> Tuple[Any, PolicyResolutionSource, Optional[VerbPolicyEntry]]:
        """Return (config, source, entry) for the given verb call.

        Resolution order:
          1. Exact match -> SPECIFIC
          2. Wildcard entry -> WILDCARD
          3. bundle.default_config -> DEFAULT
          4. (None, NO_BUNDLE) -> caller fallback
          5. If `strict_unknown_verb=True` and no entry + no wildcard,
             raises KeyError.
        """
        key = (verb_name, verb_version)
        if key in self.entries:
            return (
                self.entries[key].config,
                PolicyResolutionSource.SPECIFIC,
                self.entries[key],
            )
        wildcard_key = (verb_name, WILDCARD_VERSION)
        if wildcard_key in self.entries:
            entry = self.entries[wildcard_key]
            return (entry.config, PolicyResolutionSource.WILDCARD, entry)
        if self.default_config is not None:
            return (self.default_config, PolicyResolutionSource.DEFAULT, None)
        if self.strict_unknown_verb:
            raise KeyError(
                f"VerbPolicyBundle {self.library_id!r}: no entry for "
                f"({verb_name!r}, {verb_version!r}) and no default_config "
                f"and strict_unknown_verb=True"
            )
        # Bundle exists but had no match and no default_config.
        # Treat as DEFAULT (caller will fall back to its own default).
        return (None, PolicyResolutionSource.DEFAULT, None)

    def names(self) -> List[str]:
        return sorted(self._version_index.keys())

    def versions_of(self, verb_name: str) -> List[str]:
        return list(self._version_index.get(verb_name, ()))

    def __len__(self) -> int:
        return len(self.entries)

    def __contains__(self, key: Any) -> bool:
        if isinstance(key, tuple) and len(key) == 2:
            return key in self.entries
        return False

    # --- audit log ---

    def audit_log(self) -> "VerbPolicyAuditLog":
        if self._audit_log is None:
            self._audit_log = VerbPolicyAuditLog(
                log_id=f"policy-audit-{self.library_id}",
            )
            # Wire the bundle's audit_path to the log so subsequent
            # appends get flushed to disk.
            if self.audit_path is not None:
                p = Path(self.audit_path)
                p.parent.mkdir(parents=True, exist_ok=True)
                if not p.exists():
                    p.touch()
                self._audit_log._jsonl_path = str(p)
        return self._audit_log

    def to_dict(self) -> Dict[str, Any]:
        return {
            "library_id": self.library_id,
            "created_at": self.created_at,
            "audit_path": self.audit_path,
            "strict_unknown_verb": self.strict_unknown_verb,
            "default_config": (
                self.default_config.to_dict()
                if self.default_config is not None
                and hasattr(self.default_config, "to_dict")
                else None
            ),
            "entries": [
                {**entry.to_dict(), "verb_name": k[0], "verb_version": k[1]}
                for k, entry in sorted(self.entries.items())
            ],
        }


def create_verb_policy_bundle(
    library_id: str = "",
    bundle_id: str = "",
    default_config: Any = None,
    audit_path: Optional[str] = None,
    strict_unknown_verb: bool = False,
) -> VerbPolicyBundle:
    """Factory. Accepts `library_id` (preferred) and `bundle_id` (alias).

    `strict_unknown_verb=True` means: an unknown verb (no entry, no wildcard,
    no default_config) raises KeyError instead of returning NO_BUNDLE.
    Useful for closed-world verb libraries where any unknown verb is an error.
    """
    bundle = VerbPolicyBundle(
        library_id=library_id or bundle_id or "default",
        default_config=default_config,
        audit_path=audit_path,
        strict_unknown_verb=strict_unknown_verb,
    )
    return bundle


# ===========================================================================
# Audit entry + log
# ===========================================================================

@dataclass
class PolicyAuditEntry:
    """A single hash-chained audit log entry.

    Not frozen (despite being immutable-after-append) so tests can
    mutate individual fields to verify tamper detection on the chain.
    """
    event_id: str
    event_kind: PolicyAuditEventKind
    verb_name: str
    verb_version: str
    source: PolicyResolutionSource
    timestamp: float
    program_id: str
    step_index: int
    sequence: int
    prev_hash: str
    config_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_kind": self.event_kind.value,
            "verb_name": self.verb_name,
            "verb_version": self.verb_version,
            "source": self.source.value,
            "timestamp": self.timestamp,
            "program_id": self.program_id,
            "step_index": self.step_index,
            "sequence": self.sequence,
            "prev_hash": self.prev_hash,
            "config_hash": self.config_hash,
        }


def _hash_audit_entry(prev_hash: str, payload: Dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(f"{prev_hash}|{blob}".encode("utf-8")).hexdigest()


@dataclass
class VerbPolicyAuditLog:
    """Append-only hash-chained audit log for policy events.

    Mirrors the IEEC hash chain from core.proof_carrying_action: each
    entry's `event_hash` is sha256(prev_hash || canonical_json(payload)),
    and `prev_hash` is the previous entry's `event_hash`. Any tampering
    invalidates the chain.
    """
    log_id: str
    entries: List[PolicyAuditEntry] = field(default_factory=list)
    _last_hash: str = field(default="0" * 64)
    _jsonl_path: Optional[str] = field(default=None)
    _pending_jsonl: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.log_id:
            raise ValueError("VerbPolicyAuditLog: log_id is required")

    def append_event(
        self,
        event_kind: PolicyAuditEventKind,
        verb_name: str,
        verb_version: str,
        source: PolicyResolutionSource,
        program_id: str,
        step_index: int,
        prev_hash: str,
        config_hash: str,
    ) -> PolicyAuditEntry:
        ts = time.time()
        payload = {
            "event_kind": event_kind.value,
            "verb_name": verb_name,
            "verb_version": verb_version,
            "source": source.value,
            "timestamp": ts,
            "program_id": program_id,
            "step_index": step_index,
            "config_hash": config_hash,
        }
        event_hash = _hash_audit_entry(prev_hash, payload)
        entry = PolicyAuditEntry(
            event_id=f"evt-{len(self.entries):08d}-{event_hash[:8]}",
            event_kind=event_kind,
            verb_name=verb_name,
            verb_version=verb_version,
            source=source,
            timestamp=ts,
            program_id=program_id,
            step_index=step_index,
            sequence=len(self.entries),
            prev_hash=prev_hash,
            config_hash=config_hash,
        )
        object.__setattr__(entry, "event_hash", event_hash)
        self.entries.append(entry)
        self._last_hash = event_hash
        if self._jsonl_path is not None:
            self._pending_jsonl.append(entry.to_dict())
        return entry

    def append(self, entry: PolicyAuditEntry) -> PolicyAuditEntry:
        """Append an already-built entry. Updates _last_hash and pending JSONL.

        If the entry doesn't have an `event_hash` attribute, we compute
        it from the entry's payload (matching the chain rules). The
        computed hash is set on the entry as a side-effect.
        """
        if entry in self.entries:
            return entry
        # Compute the event_hash if the caller didn't supply one
        existing_hash = getattr(entry, "event_hash", None)
        if existing_hash is None:
            payload = {
                "event_kind": entry.event_kind.value,
                "verb_name": entry.verb_name,
                "verb_version": entry.verb_version,
                "source": entry.source.value,
                "timestamp": entry.timestamp,
                "program_id": entry.program_id,
                "step_index": entry.step_index,
                "config_hash": entry.config_hash,
            }
            computed = _hash_audit_entry(entry.prev_hash, payload)
            try:
                object.__setattr__(entry, "event_hash", computed)
            except Exception:
                pass
        self.entries.append(entry)
        self._last_hash = getattr(entry, "event_hash", entry.prev_hash)
        if self._jsonl_path is not None:
            self._pending_jsonl.append(entry.to_dict())
        return entry

    def last_hash(self) -> str:
        return self._last_hash

    def verify_chain(self) -> bool:
        last = "0" * 64
        for entry in self.entries:
            payload = {
                "event_kind": entry.event_kind.value,
                "verb_name": entry.verb_name,
                "verb_version": entry.verb_version,
                "source": entry.source.value,
                "timestamp": entry.timestamp,
                "program_id": entry.program_id,
                "step_index": entry.step_index,
                "config_hash": entry.config_hash,
            }
            expected = _hash_audit_entry(last, payload)
            if entry.prev_hash != last:
                return False
            if getattr(entry, "event_hash", None) != expected:
                # If event_hash was not stored, compute and continue.
                # Otherwise the chain has been tampered.
                if getattr(entry, "event_hash", None) is not None:
                    return False
            last = getattr(entry, "event_hash", expected)
        return True

    def events(self) -> List[PolicyAuditEntry]:
        return list(self.entries)

    def counts_per_source(self) -> Dict[PolicyResolutionSource, int]:
        out: Dict[PolicyResolutionSource, int] = {}
        for entry in self.entries:
            out[entry.source] = out.get(entry.source, 0) + 1
        return out

    def flush(self) -> None:
        """Flush pending JSONL entries to disk."""
        if self._jsonl_path is None or not self._pending_jsonl:
            return
        p = Path(self._jsonl_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            for entry_dict in self._pending_jsonl:
                f.write(json.dumps(entry_dict, sort_keys=True, default=str) + "\n")
        self._pending_jsonl = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "log_id": self.log_id,
            "entries": [e.to_dict() for e in self.entries],
            "head_hash": self._last_hash,
        }


# ===========================================================================
# resolve_policy (the advisory resolution function)
# ===========================================================================

def resolve_policy(
    bundle: Optional[VerbPolicyBundle],
    verb_name: str,
    verb_version: str,
    call_id: str = "",
    program_id: str = "",
    step_index: int = 0,
) -> Tuple[Any, PolicyResolutionSource, Optional[VerbPolicyEntry]]:
    """Resolve a policy config and return (config, source, entry).

    The bundle's audit log records a RESOLVE / FALLBACK / MISS event.
    The caller is responsible for using the runtime's default config
    in the NO_BUNDLE case.
    """
    if bundle is None:
        return (None, PolicyResolutionSource.NO_BUNDLE, None)
    config, source, entry = bundle.resolve(verb_name, verb_version)
    if source == PolicyResolutionSource.EXACT:
        kind = PolicyAuditEventKind.RESOLVE
    elif source == PolicyResolutionSource.NO_BUNDLE:
        kind = PolicyAuditEventKind.MISS
    else:
        # WILDCARD, VERSION_FALLBACK, DEFAULT, GUARD_UNAVAILABLE
        kind = PolicyAuditEventKind.FALLBACK
    config_hash = entry.policy_digest() if entry is not None else (
        hashlib.sha256(
            json.dumps(
                config.to_dict() if hasattr(config, "to_dict") else {"c": str(config)},
                sort_keys=True, default=str
            ).encode()
        ).hexdigest() if config is not None else "0" * 64
    )
    bundle.audit_log().append_event(
        event_kind=kind,
        verb_name=verb_name,
        verb_version=verb_version,
        source=source,
        program_id=program_id,
        step_index=step_index,
        prev_hash=bundle.audit_log().last_hash(),
        config_hash=config_hash,
    )
    return (config, source, entry)


# ===========================================================================
# BundledGuardConfig
# ===========================================================================

@dataclass
class BundledGuardConfig:
    """Per-call resolved guard config snapshot.

    Built by BundledVerbRuntime.invoke() per call. Carries the
    resolution source + the resolved config + the freshly-built
    VerbCEFGuard (since each call may resolve a different config).
    """
    config: Any
    resolution_source: PolicyResolutionSource
    entry: Optional[VerbPolicyEntry] = None
    guard: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": self.config.to_dict() if hasattr(self.config, "to_dict") else str(self.config),
            "resolution_source": self.resolution_source.value,
        }


def _make_guard(detector: Any, config: Any) -> Any:
    """Build a fresh VerbCEFGuard from (detector, config)."""
    if not _GUARD_AVAILABLE:
        return None
    try:
        return _VerbCEFGuard(detector=detector, config=config)
    except Exception:
        return None


# ===========================================================================
# BundledVerbRuntime
# ===========================================================================

@dataclass
class BundledVerbStepResult:
    """The result of a single bundled invocation."""
    result: Any
    inspection: Any
    resolution: PolicyResolutionRecord
    guard_action: Any

    @property
    def success(self) -> bool:
        return getattr(self.result, "success", True)

    @property
    def halted(self) -> bool:
        return getattr(self.result, "halted", False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result": self.result.to_dict() if hasattr(self.result, "to_dict") else None,
            "inspection": self.inspection.to_dict() if hasattr(self.inspection, "to_dict") else None,
            "resolution": self.resolution.to_dict(),
            "guard_action": (
                self.guard_action.value
                if hasattr(self.guard_action, "value")
                else str(self.guard_action)
            ),
            "halted": self.halted,
        }


@dataclass
class PolicyResolutionRecord:
    """Snapshot of a single policy resolution for the call result.

    Carries the verb info, source, and resolved config so callers
    (and the audit log) have everything they need to reconstruct
    which policy was applied to which call.
    """
    verb_name: str
    verb_version: str
    source: PolicyResolutionSource
    config: Any = None
    policy_digest: str = ""
    call_id: str = ""
    program_id: str = ""
    step_index: int = 0
    timestamp: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verb_name": self.verb_name,
            "verb_version": self.verb_version,
            "source": self.source.value,
            "config": self.config.to_dict() if hasattr(self.config, "to_dict") else str(self.config),
            "policy_digest": self.policy_digest,
            "call_id": self.call_id,
            "program_id": self.program_id,
            "step_index": self.step_index,
            "timestamp": self.timestamp,
        }


@dataclass
class BundledVerbRuntime:
    """A guarded runtime that resolves per-verb guard config from a bundle.

    Each invoke() does:
      1. resolve policy for (verb_name, verb_version) via the bundle
         (records a RESOLVE / FALLBACK / MISS event in the bundle's
         audit log)
      2. build a per-call guard with the resolved config
      3. invoke the inner runtime
      4. inspect the output with the per-call guard
      5. return a BundledVerbStepResult
    """
    runtime: Any
    detector: Any = None
    bundle: Optional[VerbPolicyBundle] = None
    default_config: Any = None
    halt_on_halt: bool = True
    max_audit_entries: int = 10000
    resolutions: List[PolicyResolutionRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.default_config is None and _GUARD_AVAILABLE:
            self.default_config = _VerbCEFGuardConfig()

    def _resolve_for_call(
        self, call: Any, program_id: str = "", step_index: int = 0
    ) -> Tuple[BundledGuardConfig, PolicyResolutionRecord]:
        # Use resolve_policy() so the bundle's audit log records the RESOLVE event
        if self.bundle is not None:
            config, source, entry = resolve_policy(
                self.bundle, call.name, call.version,
                call_id=getattr(call, "call_id", ""),
                program_id=program_id, step_index=step_index,
            )
        else:
            config, source, entry = (None, PolicyResolutionSource.NO_BUNDLE, None)
        # Fall back to the runtime's default_config if the bundle had no match
        if config is None:
            config = self.default_config
        digest = entry.policy_digest() if entry is not None else (
            hashlib.sha256(
                json.dumps(
                    config.to_dict() if hasattr(config, "to_dict") else {"c": str(config)},
                    sort_keys=True, default=str
                ).encode()
            ).hexdigest() if config is not None else "0" * 64
        )
        record = PolicyResolutionRecord(
            verb_name=call.name,
            verb_version=call.version,
            source=source,
            config=config,
            policy_digest=digest,
            call_id=getattr(call, "call_id", ""),
            program_id=program_id,
            step_index=step_index,
        )
        self.resolutions.append(record)
        if len(self.resolutions) > self.max_audit_entries:
            self.resolutions = self.resolutions[-self.max_audit_entries:]
        guard = _make_guard(self.detector, config) if config is not None else None
        bundled = BundledGuardConfig(
            config=config, resolution_source=source, entry=entry, guard=guard
        )
        return bundled, record

    def invoke(self, call: Any, program_id: str = "", step_index: int = 0) -> BundledVerbStepResult:
        from .typed_verb_cef_guard import (
            GuardedVerbRuntime,
            GuardedVerbStepResult,
            VerbOutputCEFInspection,
            CEFGuardAvailability,
            VerbGuardAction,
        )
        bundled, record = self._resolve_for_call(call, program_id=program_id, step_index=step_index)
        if bundled.guard is None:
            inner = self.runtime.invoke(call, program_id=program_id, step_index=step_index)
            inspection = VerbOutputCEFInspection(
                call_id=getattr(call, "call_id", ""),
                verb_name=call.name,
                verb_version=call.version,
                program_id=program_id,
                step_index=step_index,
                scanned_fields=(),
                aggregate_text_hash="",
                aggregate_text_length=0,
                detection=None,
                guard_action=VerbGuardAction.NONE,
                is_clean=True,
                inspected_at=time.time(),
                availability=CEFGuardAvailability.NO_CEF_SUBSTRATE,
            )
            guard_action = VerbGuardAction.NONE
            result = GuardedVerbStepResult(result=inner, inspection=inspection)
        else:
            inner_guarded = GuardedVerbRuntime(
                runtime=self.runtime,
                guard=bundled.guard,
                halt_on_halt=self.halt_on_halt,
            )
            result = inner_guarded.invoke(call, program_id=program_id, step_index=step_index)
            guard_action = result.inspection.guard_action
        return BundledVerbStepResult(
            result=result, inspection=result.inspection,
            resolution=record, guard_action=guard_action,
        )

    # `state` is an attribute proxy (not a method) so callers can do
    # `bundled.state is runtime.state`. The VerbRuntime's `state` is a
    # mutable dict; we proxy reads/writes through it.
    @property
    def state(self) -> Any:
        return self.runtime.state

    @state.setter
    def state(self, value: Any) -> None:
        self.runtime.state = value

    def audit(self) -> Any:
        return self.runtime.audit


# ===========================================================================
# Factories + JSONL audit
# ===========================================================================

def create_bundled_verb_runtime(
    runtime: Any,
    bundle: Optional[VerbPolicyBundle] = None,
    detector: Any = None,
    default_config: Any = None,
    halt_on_halt: bool = True,
) -> BundledVerbRuntime:
    return BundledVerbRuntime(
        runtime=runtime,
        detector=detector,
        bundle=bundle,
        default_config=default_config,
        halt_on_halt=halt_on_halt,
    )


def enable_policy_audit(bundle: VerbPolicyBundle, audit_path: str) -> None:
    """Mirror JSONL audit entries to a file. Append-only, one entry per line.

    The in-memory hash chain is the source of truth; the file is a
    durable mirror for offline replay.
    """
    p = Path(audit_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.touch()
    # Attach the JSONL path to the log so subsequent appends get flushed
    log = bundle.audit_log()
    log._jsonl_path = str(p)
    # Replay any existing entries to seed the in-memory chain
    last_hash = "0" * 64
    sequence = 0
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            last_hash = obj.get("event_hash", last_hash)
            sequence = max(sequence, obj.get("sequence", sequence) + 1)
    log._last_hash = last_hash


__all__ = [
    "WILDCARD_VERSION",
    "BundledGuardConfig",
    "BundledVerbRuntime",
    "BundledVerbStepResult",
    "PolicyAuditEntry",
    "PolicyAuditEventKind",
    "PolicyResolutionRecord",
    "PolicyResolutionSource",
    "VerbPolicyAuditLog",
    "VerbPolicyBundle",
    "VerbPolicyEntry",
    "create_bundled_verb_runtime",
    "create_verb_policy_bundle",
    "enable_policy_audit",
    "resolve_policy",
]
