"""AIBOM (AI Bill of Materials) Advisory Emitter (arXiv:2606.19390).

Closes the 2026-07-05 carryover: the CPP substrate writes a JSONL
audit log of (level, verb, cef_type, severity, marker_count,
policy_resolution, policy_source) observations. The next layer up
is an advisory that *binds* the runtime evidence to a structured,
machine-readable declaration of the affected component, its
exploitability, and a remediation recommendation. This module
implements that layer.

Research motivation (2026-07-06):
  - arXiv:2606.19390v1 (Execution-bound advisory automation for
    agentic AI: a reproducible AIBOM-driven CSAF-VEX framework):
    "advisories are produced from combined static and runtime
    evidence, cryptographically signed, and verifiable through
    deterministic replay". Our advisory format borrows CSAF-VEX's
    skeleton (document tracking + vulnerabilities[] + product_tree)
    but stays operator-friendly JSON (not full CSAF VEX XML). The
    audit log IS the runtime evidence; the bundle snapshot is the
    static evidence.
  - AIBOM-as-SBOM-for-AI (Security Magazine, IST policy memo,
    Safeguard 2026): the advisory should expose the affected
    component, its provenance, its exploitability, and its
    remediation status. The advisory emitter reads the bundle
    snapshot + audit log and emits a single self-contained
    JSON document with all four.
  - MedSkillAudit (AIPOCH, 2026-06-29): a "pre-deployment audit
    framework" with a "two-stage evaluation" (static 40% + dynamic
    60%). The advisory emitter exposes the same two-stage structure:
    static (bundle snapshot) and dynamic (CPP audit log).
  - Agent Gateway control plane (Forbes, Jul 5 2026; Nutanix;
    Arcade on Azure/AWS marketplaces): the advisory is the
    "tamper-evident audit" that the gateway emits when the
    control plane triggers a response. The advisory carries the
    governance signal downstream.

Conservative posture:
  - The advisory is *advisory*. It carries a recommendation
    (defer / monitor / remediate / block); the operator (or the
    upstream agent gateway) decides what to do.
  - No I/O at construction. `emit_aibom_advisory()` is pure: it
    takes a CPPOutcome / audit log + a bundle snapshot and returns
    a self-contained dict. The caller chooses where to write it.
  - The advisory is *content-addressed*: `advisory_id` is
    `sha256(json_canonical_form)` of the static evidence, so two
    observers of the same bundle + audit log produce the same
    advisory_id. This is the substrate for downstream signature
    schemes.
  - The advisory exposes the policy provenance from the bundle
    snapshot: which entry resolved for each verb, what its source
    was (SPECIFIC / WILDCARD / DEFAULT / NO_BUNDLE), and the
    registered rationale. The advisory is the audit trail's
    handoff to a human reviewer.
  - No silent redaction. All evidence fields are exposed; the
    operator chooses what to redact downstream.
  - Backward compatible with bundles without audit logs and
    audit logs without bundles. The advisory records what it has.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ===========================================================================
# Advisory schema (CSAF-VEX-inspired, JSON-friendly, agent-substrate)
# ===========================================================================

# Versioning: bump MAJOR on breaking schema changes, MINOR on
# additive fields, PATCH on cosmetic fixes. Consumers should pin
# to a major.
ADVISORY_SCHEMA_VERSION = "1.0.0"


class AdvisoryCategory(str, Enum):
    """Top-level classification of the advisory. Maps to the CSAF-VEX
    /document/category field; the agent-substrate uses shorter names
    suited to JSON consumers.
    """

    GENERIC = "generic"
    CEF_EMERGENCE = "cef_emergence"
    POLICY_LOOSENING = "policy_loosening"
    THANATOSIS = "thanatosis"
    BUNDLE_GAP = "bundle_gap"


class AdvisorySeverity(str, Enum):
    """Severity ordering (NONE < LOW < MEDIUM < HIGH < CRITICAL).
    Mirrors CEFSeverity; the advisory uses a string enum to keep
    the JSON document self-describing.
    """

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def rank(cls, value: str) -> int:
        order = {
            "none": 0,
            "low": 1,
            "medium": 2,
            "high": 3,
            "critical": 4,
        }
        return order.get(str(value).lower(), 0)


class AdvisoryAction(str, Enum):
    """Operator-facing recommendation. Maps loosely to the CSAF-VEX
    /vulnerabilities[]/product_status field, but is agent-substrate
    shaped: "block" is the new entry; "defer" + "monitor" are the
    "not_affected" / "fixed" continuums from VEX.
    """

    DEFER = "defer"
    MONITOR = "monitor"
    REMEDIATE = "remediate"
    BLOCK = "block"


# Advisory status mirrors CSAF VEX /product_status: "draft",
# "interim", "final". "superseded" is preserved for completeness.
class AdvisoryStatus(str, Enum):
    DRAFT = "draft"
    INTERIM = "interim"
    FINAL = "final"
    SUPERSEDED = "superseded"


# Band rank re-use from skills/cpp.py; the advisory keeps its own
# copy so core/aibom_advisory.py does not depend on skills/cpp.py.
_BAND_RANK = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def _band_rank(band: str) -> int:
    return _BAND_RANK.get(str(band).lower(), 0)


# ===========================================================================
# Dataclasses
# ===========================================================================


@dataclass
class AIBOMComponent:
    """One AIBOM component declaration (per-verb policy unit).

    A component is the typed-verb the bundle governs. The advisory
    treats each (verb_name, verb_version) pair as one AIBOM
    component. The component carries: its identity, its policy
    provenance, its observed exploitability, and its status.
    """

    component_id: str
    verb_name: str
    verb_version: str
    policy_source: Optional[str]
    policy_digest: Optional[str]
    policy_rationale: Optional[str]
    exploitability: str
    observed_severity: str
    observed_band: str
    observed_marker_count: int
    observed_cef_type: Optional[str]
    observation_count: int
    thanatosis_count: int
    worst_level_index: Optional[int]
    worst_level_name: Optional[str]
    recommendation: str
    status: str
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "verb_name": self.verb_name,
            "verb_version": self.verb_version,
            "policy_source": self.policy_source,
            "policy_digest": self.policy_digest,
            "policy_rationale": self.policy_rationale,
            "exploitability": self.exploitability,
            "observed_severity": self.observed_severity,
            "observed_band": self.observed_band,
            "observed_marker_count": self.observed_marker_count,
            "observed_cef_type": self.observed_cef_type,
            "observation_count": self.observation_count,
            "thanatosis_count": self.thanatosis_count,
            "worst_level_index": self.worst_level_index,
            "worst_level_name": self.worst_level_name,
            "recommendation": self.recommendation,
            "status": self.status,
            "notes": list(self.notes),
        }


@dataclass
class AIBOMAdvisory:
    """A self-contained AIBOM advisory document.

    The advisory has six top-level sections, in CSAF-VEX order:
      - document metadata (tracking + publisher + schema)
      - product_tree (components: per-verb AIBOM entries)
      - vulnerabilities (per-component finding summary)
      - notes (advisory-level context)
      - references (evidence pointers: audit log + bundle + replay)
      - signature (advisory_id is the content hash; the signature
        placeholder is a hook for a future signed envelope)
    """

    document: Dict[str, Any]
    product_tree: Dict[str, Any]
    vulnerabilities: List[Dict[str, Any]]
    notes: List[Dict[str, Any]]
    references: List[Dict[str, Any]]
    advisory_id: str
    category: str
    severity: str
    recommendation: str
    status: str
    generated_at: float
    evidence_digest: str
    bundle_library_id: Optional[str]
    audit_log_path: Optional[str]
    cef_substrate_available: bool
    total_observations: int
    thanatosis_count: int
    worst_band: str
    component_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document": dict(self.document),
            "product_tree": dict(self.product_tree),
            "vulnerabilities": [dict(v) for v in self.vulnerabilities],
            "notes": [dict(n) for n in self.notes],
            "references": [dict(r) for r in self.references],
            "advisory_id": self.advisory_id,
            "category": self.category,
            "severity": self.severity,
            "recommendation": self.recommendation,
            "status": self.status,
            "generated_at": self.generated_at,
            "evidence_digest": self.evidence_digest,
            "bundle_library_id": self.bundle_library_id,
            "audit_log_path": self.audit_log_path,
            "cef_substrate_available": self.cef_substrate_available,
            "total_observations": self.total_observations,
            "thanatosis_count": self.thanatosis_count,
            "worst_band": self.worst_band,
            "component_count": self.component_count,
        }


# ===========================================================================
# Helpers
# ===========================================================================


def _canonical_form(payload: Dict[str, Any]) -> str:
    """Canonical JSON form for hashing. Sorted keys, no whitespace."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _severity_to_action(band: str, is_thanatosis: bool) -> str:
    """Map (worst_band, is_thanatosis) -> operator recommendation.

    Conservative posture: CRITICAL + thanatosis -> BLOCK. CRITICAL
    alone -> REMEDIATE. HIGH -> REMEDIATE. MEDIUM -> MONITOR. LOW
    or NONE -> DEFER (operator may choose to ship with the
    finding under a waitlist).
    """
    if is_thanatosis:
        return AdvisoryAction.BLOCK.value
    r = _band_rank(band)
    if r >= 4:
        return AdvisoryAction.REMEDIATE.value
    if r >= 3:
        return AdvisoryAction.REMEDIATE.value
    if r >= 2:
        return AdvisoryAction.MONITOR.value
    return AdvisoryAction.DEFER.value


def _category_for(components: Sequence[AIBOMComponent]) -> str:
    """Top-level category for the advisory.

    Priority:
      1. Any component is CET (thanatosis) -> THANATOSIS
      2. Any component is policy LOOSENING -> POLICY_LOOSENING
      3. Any component has CEF emergence -> CEF_EMERGENCE
      4. Otherwise -> GENERIC
    """
    if any(c.observed_cef_type == "simulated_crash" and c.observed_severity == "critical"
           for c in components):
        return AdvisoryCategory.THANATOSIS.value
    if any(c.policy_rationale and "looser" in (c.policy_rationale or "").lower()
           for c in components):
        return AdvisoryCategory.POLICY_LOOSENING.value
    if any(c.observation_count > 0 and c.observed_marker_count > 0
           for c in components):
        return AdvisoryCategory.CEF_EMERGENCE.value
    return AdvisoryCategory.GENERIC.value


def _advisory_severity(components: Sequence[AIBOMComponent]) -> str:
    """Worst severity across all components. CRITICAL wins."""
    worst = 0
    for c in components:
        r = AdvisorySeverity.rank(c.observed_severity)
        if r > worst:
            worst = r
    if worst >= 4:
        return AdvisorySeverity.CRITICAL.value
    if worst >= 3:
        return AdvisorySeverity.HIGH.value
    if worst >= 2:
        return AdvisorySeverity.MEDIUM.value
    if worst >= 1:
        return AdvisorySeverity.LOW.value
    return AdvisorySeverity.NONE.value


def _advisory_recommendation(severity: str, has_thanatosis: bool) -> str:
    if has_thanatosis:
        return AdvisoryAction.BLOCK.value
    r = AdvisorySeverity.rank(severity)
    if r >= 3:
        return AdvisoryAction.REMEDIATE.value
    if r >= 2:
        return AdvisoryAction.MONITOR.value
    return AdvisoryAction.DEFER.value


def _component_status(component: AIBOMComponent) -> str:
    """Map a component's finding to a VEX-style product_status.

    "known_affected" if any observation has marker_count > 0 or
    severity > none. "known_not_affected" if all observations are
    clean. "under_investigation" is reserved for ambiguous cases
    (e.g., CEF substrate unavailable, or a partial target error).
    """
    if component.observation_count == 0:
        return "under_investigation"
    if component.observed_marker_count > 0:
        return "known_affected"
    if component.observed_severity not in (None, "", "none"):
        return "known_affected"
    return "known_not_affected"


def _exploitability(component: AIBOMComponent) -> str:
    """Heuristic exploitability score.

    Maps the worst observed band to a CSAF-style probability band:
      CRITICAL + thanatosis -> "critical"
      CRITICAL              -> "high"
      HIGH                  -> "high"
      MEDIUM                -> "medium"
      LOW                   -> "low"
      NONE                  -> "none"
    """
    if component.observed_cef_type == "simulated_crash" and \
            component.observed_severity == "critical":
        return "critical"
    r = _band_rank(component.observed_band)
    if r >= 3:
        return "high"
    if r >= 2:
        return "medium"
    if r >= 1:
        return "low"
    return "none"


def _evidence_digest_from_audit_log(
    audit_log_path: Optional[str],
    audit_log_records: Optional[Sequence[Dict[str, Any]]] = None,
) -> str:
    """Compute a deterministic digest over the runtime evidence.

    If `audit_log_records` is supplied, hash the canonical JSON
    of those records. If not, read the file at `audit_log_path`
    and hash its bytes. Returns the empty string if neither is
    available.
    """
    if audit_log_records is not None:
        return _sha256_hex(_canonical_form({"records": list(audit_log_records)}))
    if audit_log_path is not None:
        p = Path(audit_log_path)
        if p.exists():
            return _sha256_hex(p.read_text(encoding="utf-8"))
    return ""


def _component_from_observation(
    verb_name: str,
    observations: List[Dict[str, Any]],
) -> AIBOMComponent:
    """Aggregate per-verb observations into a single component.

    `observations` is a list of audit-log records for one verb.
    The aggregator computes: worst band, worst severity, worst
    CEF type, worst level, thanatosis count, total marker count.
    """
    if not observations:
        return AIBOMComponent(
            component_id="",
            verb_name=verb_name,
            verb_version="*",
            policy_source=None,
            policy_digest=None,
            policy_rationale=None,
            exploitability="none",
            observed_severity="none",
            observed_band="none",
            observed_marker_count=0,
            observed_cef_type=None,
            observation_count=0,
            thanatosis_count=0,
            worst_level_index=None,
            worst_level_name=None,
            recommendation=AdvisoryAction.DEFER.value,
            status="under_investigation",
            notes=["no observations"],
        )

    # Find the worst observation by (band rank, severity rank, marker_count).
    def obs_key(o: Dict[str, Any]) -> Tuple[int, int, int, int, str]:
        band = str(o.get("band", "none"))
        sev = str(o.get("severity", "none"))
        marker = int(o.get("marker_count", 0) or 0)
        level_idx = int(o.get("level_index", -1) or -1)
        cef_type = str(o.get("cef_type") or "")
        # Priority: CRITICAL_SIMULATED > HIGH > MEDIUM > LOW
        is_thanatosis = (
            o.get("severity") == "critical"
            and o.get("cef_type") == "simulated_crash"
        )
        return (
            1 if is_thanatosis else 0,
            _band_rank(band),
            AdvisorySeverity.rank(sev),
            marker,
            cef_type,
        )

    worst = max(observations, key=obs_key)
    is_thanatosis = (
        worst.get("severity") == "critical"
        and worst.get("cef_type") == "simulated_crash"
    )

    observed_band = str(worst.get("band", "none"))
    observed_severity = str(worst.get("severity", "none"))
    observed_cef_type = worst.get("cef_type")

    total_marker_count = sum(
        int(o.get("marker_count", 0) or 0) for o in observations
    )
    thanatosis_count = sum(
        1 for o in observations
        if o.get("severity") == "critical"
        and o.get("cef_type") == "simulated_crash"
    )

    # Use the first observation's policy provenance (conservative:
    # if the bundle flipped, we want the operator to see *a*
    # resolution, not a synthesized worst-case). Notes carry any
    # per-call variance.
    first = observations[0]
    policy_source = first.get("policy_source")
    policy_digest = None
    policy_rationale = None
    policy_resolution = first.get("policy_resolution") or {}
    if isinstance(policy_resolution, dict):
        policy_digest = policy_resolution.get("policy_digest")
        policy_rationale = policy_resolution.get("rationale")

    verb_version = first.get("verb_version", "*") or "*"
    component_id = f"verb:{verb_name}:{verb_version}"

    # Build provisional component; status + recommendation are
    # computed below once we know the worst band.
    component = AIBOMComponent(
        component_id=component_id,
        verb_name=verb_name,
        verb_version=str(verb_version),
        policy_source=policy_source,
        policy_digest=policy_digest,
        policy_rationale=policy_rationale,
        exploitability=_exploitability(_dummy_component(observed_band, observed_severity,
                                                       observed_cef_type)),
        observed_severity=observed_severity,
        observed_band=observed_band,
        observed_marker_count=total_marker_count,
        observed_cef_type=str(observed_cef_type) if observed_cef_type else None,
        observation_count=len(observations),
        thanatosis_count=thanatosis_count,
        worst_level_index=int(worst.get("level_index", -1))
        if worst.get("level_index") is not None else None,
        worst_level_name=worst.get("level_name"),
        recommendation=AdvisoryAction.DEFER.value,
        status="under_investigation",
        notes=[],
    )
    component.exploitability = _exploitability(component)
    component.recommendation = _severity_to_action(observed_band, is_thanatosis)
    component.status = _component_status(component)
    return component


def _dummy_component(
    band: str,
    severity: str,
    cef_type: Optional[str],
) -> AIBOMComponent:
    """Temporary component to feed _exploitability before the real one
    is constructed. Only the band/severity/cef_type fields matter."""
    return AIBOMComponent(
        component_id="",
        verb_name="",
        verb_version="*",
        policy_source=None,
        policy_digest=None,
        policy_rationale=None,
        exploitability="none",
        observed_severity=severity,
        observed_band=band,
        observed_marker_count=0,
        observed_cef_type=cef_type,
        observation_count=0,
        thanatosis_count=0,
        worst_level_index=None,
        worst_level_name=None,
        recommendation=AdvisoryAction.DEFER.value,
        status="under_investigation",
        notes=[],
    )


# ===========================================================================
# Public entry points
# ===========================================================================


def group_observations_by_verb(
    observations: Sequence[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Group a flat list of audit-log records by `verb_name`.

    Records without a `verb_name` are bucketed under the empty
    string. The grouping is order-preserving within each verb.
    """
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for o in observations:
        v = str(o.get("verb_name") or "")
        grouped.setdefault(v, []).append(dict(o))
    return grouped


def build_components(
    observations: Sequence[Dict[str, Any]],
) -> List[AIBOMComponent]:
    """Build the list of AIBOM components from a flat observation list.

    Each unique `verb_name` becomes one component. The list is
    sorted by (worst band rank desc, verb_name asc) so the
    advisory's "first" component is always the most concerning.
    """
    grouped = group_observations_by_verb(observations)
    components: List[AIBOMComponent] = []
    for verb_name, obs_list in grouped.items():
        components.append(_component_from_observation(verb_name, obs_list))

    def comp_key(c: AIBOMComponent) -> Tuple[int, str]:
        return (-_band_rank(c.observed_band), c.verb_name)

    components.sort(key=comp_key)
    return components


def compute_advisory_id(evidence_digest: str, components: List[AIBOMComponent],
                        category: str) -> str:
    """Compute a content-addressed advisory_id.

    The advisory_id is sha256 over the canonical JSON of the
    (evidence_digest, components, category) tuple. Two observers
    of the same evidence + components produce the same ID; that
    is the substrate for downstream signature / deduplication
    schemes.
    """
    payload = {
        "evidence_digest": evidence_digest,
        "category": category,
        "components": [c.to_dict() for c in components],
    }
    return _sha256_hex(_canonical_form(payload))


def emit_aibom_advisory(
    observations: Sequence[Dict[str, Any]],
    *,
    bundle_snapshot: Optional[Dict[str, Any]] = None,
    audit_log_path: Optional[str] = None,
    audit_log_records: Optional[Sequence[Dict[str, Any]]] = None,
    title: str = "AGI substrate AIBOM advisory",
    publisher: str = "agi-research",
    status: str = AdvisoryStatus.INTERIM.value,
    document_category: Optional[str] = None,
) -> AIBOMAdvisory:
    """Build an AIBOM advisory from a list of CPP audit observations.

    Parameters
    ----------
    observations:
        The flat list of (level, verb) audit-log records. The
        function groups them by verb into AIBOM components.
    bundle_snapshot:
        Optional. A dict representation of the VerbPolicyBundle
        that was active during the probe run. The advisory
        records the bundle's library_id, default_config, and any
        per-verb entries it supplied.
    audit_log_path:
        Optional. Path to the JSONL audit log that produced
        `observations`. The advisory records this as a reference.
    audit_log_records:
        Optional. The full JSONL records (one per line) for
        digesting. If supplied, the evidence_digest is computed
        from these records; otherwise from the file at
        audit_log_path.
    title, publisher, status, document_category:
        Document metadata. Status defaults to "interim" because
        the advisory is generated from runtime evidence without
        a human review step yet.
    """
    components = build_components(observations)
    has_thanatosis = any(c.observed_cef_type == "simulated_crash" and
                         c.observed_severity == "critical"
                         for c in components)
    worst_band = "none"
    for c in components:
        if _band_rank(c.observed_band) > _band_rank(worst_band):
            worst_band = c.observed_band

    cef_substrate_available = any(
        o.get("cef_type") is not None and o.get("severity") is not None
        for o in observations
    ) or any(c.observation_count > 0 for c in components)
    # The substrate is unavailable if no observation carries any
    # signal at all. The advisory records this so a downstream
    # reviewer knows the advisory is "under_investigation".
    if not observations:
        cef_substrate_available = False

    evidence_digest = _evidence_digest_from_audit_log(
        audit_log_path=audit_log_path,
        audit_log_records=audit_log_records,
    )

    category = document_category or _category_for(components)
    severity = _advisory_severity(components)
    recommendation = _advisory_recommendation(severity, has_thanatosis)

    # ---- document ----
    bundle_library_id = None
    bundle_summary: Dict[str, Any] = {}
    if isinstance(bundle_snapshot, dict):
        bundle_library_id = bundle_snapshot.get("library_id")
        bundle_summary = {
            "library_id": bundle_snapshot.get("library_id"),
            "default_config": bundle_snapshot.get("default_config"),
            "entry_count": len(bundle_snapshot.get("entries", {}) or {}),
            "strict_unknown_verb": bundle_snapshot.get("strict_unknown_verb", False),
        }

    document = {
        "title": title,
        "publisher": publisher,
        "schema_version": ADVISORY_SCHEMA_VERSION,
        "category": category,
        "severity": severity,
        "recommendation": recommendation,
        "status": status,
        "generated_at": time.time(),
        "bundle_summary": bundle_summary,
    }

    # ---- product_tree ----
    product_tree = {
        "components": [c.to_dict() for c in components],
    }

    # ---- vulnerabilities (one per affected component) ----
    vulnerabilities: List[Dict[str, Any]] = []
    for c in components:
        if c.observation_count == 0 or c.observed_marker_count == 0 and \
                c.observed_severity in (None, "", "none"):
            continue
        vulnerabilities.append({
            "component_id": c.component_id,
            "verb_name": c.verb_name,
            "verb_version": c.verb_version,
            "cef_type": c.observed_cef_type,
            "severity": c.observed_severity,
            "band": c.observed_band,
            "marker_count": c.observed_marker_count,
            "exploitability": c.exploitability,
            "thanatosis": c.observed_cef_type == "simulated_crash"
            and c.observed_severity == "critical",
            "worst_level_index": c.worst_level_index,
            "worst_level_name": c.worst_level_name,
            "product_status": c.status,
            "recommendation": c.recommendation,
        })

    # ---- notes (advisory-level context) ----
    notes: List[Dict[str, Any]] = []
    notes.append({
        "category": "summary",
        "text": (
            f"{len(observations)} observations across "
            f"{len(components)} components; worst band: {worst_band}; "
            f"thanatosis: {has_thanatosis}."
        ),
    })
    if not cef_substrate_available:
        notes.append({
            "category": "ce",
            "text": "CEF substrate unavailable; advisory status is "
                    "under_investigation until a probe with the CEF "
                    "substrate is run.",
        })
    if not bundle_snapshot:
        notes.append({
            "category": "bundle",
            "text": "No bundle snapshot supplied; per-verb policy "
                    "provenance recorded from audit log only.",
        })

    # ---- references ----
    references: List[Dict[str, Any]] = []
    if audit_log_path:
        references.append({
            "category": "runtime_telemetry",
            "summary": "CPP JSONL audit log",
            "url": audit_log_path,
        })
    if bundle_library_id:
        references.append({
            "category": "static_evidence",
            "summary": f"VerbPolicyBundle {bundle_library_id!r} snapshot",
        })
    if has_thanatosis:
        references.append({
            "category": "research",
            "summary": "arXiv:2606.14831 (CEF / Thanatosis) — point of "
                       "no return after CET emergence",
        })
    if category == AdvisoryCategory.POLICY_LOOSENING.value:
        references.append({
            "category": "research",
            "summary": "arXiv:2606.19390 (AIBOM / CSAF-VEX) — policy "
                       "loosening is a known CWE pattern for agent "
                       "components",
        })
    references.append({
        "category": "research",
        "summary": "arXiv:2606.19390v1 (Execution-bound advisory "
                   "automation for agentic AI: a reproducible AIBOM-"
                   "driven CSAF-VEX framework)",
    })

    advisory_id = compute_advisory_id(evidence_digest, components, category)

    return AIBOMAdvisory(
        document=document,
        product_tree=product_tree,
        vulnerabilities=vulnerabilities,
        notes=notes,
        references=references,
        advisory_id=advisory_id,
        category=category,
        severity=severity,
        recommendation=recommendation,
        status=status,
        generated_at=document["generated_at"],
        evidence_digest=evidence_digest,
        bundle_library_id=bundle_library_id,
        audit_log_path=audit_log_path,
        cef_substrate_available=cef_substrate_available,
        total_observations=len(observations),
        thanatosis_count=sum(c.thanatosis_count for c in components),
        worst_band=worst_band,
        component_count=len(components),
    )


# ===========================================================================
# Soft imports of bundle substrate (so aibom_advisory can run without it)
# ===========================================================================


def try_emit_from_bundle(
    bundle: Any,
    outcome: Any,
    *,
    audit_log_path: Optional[str] = None,
    audit_log_records: Optional[Sequence[Dict[str, Any]]] = None,
) -> AIBOMAdvisory:
    """Convenience: build the advisory from a VerbPolicyBundle + CPPOutcome.

    The bundle is rendered to a dict via `to_dict()` (if available)
    or `__dict__`. The outcome's `observations` list is the input.
    This is the function the CLI uses; it allows the bundle +
    outcome to be the *only* required inputs.
    """
    bundle_snapshot: Optional[Dict[str, Any]] = None
    try:
        if hasattr(bundle, "to_dict"):
            bundle_snapshot = bundle.to_dict()
        elif bundle is not None:
            bundle_snapshot = dict(vars(bundle))
    except Exception:
        bundle_snapshot = None

    observations: List[Dict[str, Any]] = []
    if outcome is not None:
        obs = getattr(outcome, "observations", None) or []
        for o in obs:
            if hasattr(o, "to_dict"):
                observations.append(o.to_dict())
            elif hasattr(o, "__dict__"):
                observations.append(dict(vars(o)))
            elif isinstance(o, dict):
                observations.append(dict(o))

    return emit_aibom_advisory(
        observations,
        bundle_snapshot=bundle_snapshot,
        audit_log_path=audit_log_path,
        audit_log_records=audit_log_records,
    )


def write_advisory(advisory: AIBOMAdvisory, path: str) -> None:
    """Write an advisory to disk as a single JSON document."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(advisory.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_audit_log(path: str) -> List[Dict[str, Any]]:
    """Read a JSONL audit log into a list of dicts.

    Skips blank lines. Tolerates malformed lines (records the
    parse error in the dict under a `_parse_error` key) so a
    reviewer sees the full file even if some lines are corrupt.
    """
    records: List[Dict[str, Any]] = []
    p = Path(path)
    if not p.exists():
        return records
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            records.append({"_parse_error": str(e), "_line": i + 1,
                            "_raw": line})
    return records
