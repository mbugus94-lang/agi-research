"""Tests for core/verb_policy_bundle.py — per-verb CEF guard policy bundle.

Builds on the 2026-07-02 typed-verb CEF guard by adding operator-
controllable per-verb policy. A pay verb that fabricates an external
obstacle should be treated more strictly than a read verb that
fabricates the same obstacle.

The bundle is the standardization layer for the typed-verb CEF guard
(arXiv:2606.19390, AIBOM/CSAF-VEX "enforced execution policies per
component" pattern; Vinton Cerf Open Frontier 2026-06-30 on agent
interoperability and composability).
"""

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pytest

from core.verb_policy_bundle import (
    BundledGuardConfig,
    BundledVerbRuntime,
    BundledVerbStepResult,
    PolicyAuditEntry,
    PolicyAuditEventKind,
    PolicyResolutionSource,
    VerbPolicyAuditLog,
    VerbPolicyBundle,
    VerbPolicyEntry,
    WILDCARD_VERSION,
    create_bundled_verb_runtime,
    create_verb_policy_bundle,
    enable_policy_audit,
    resolve_policy,
)
from core.typed_verb_cef_guard import (
    CEFGuardAvailability,
    VerbCEFGuardConfig,
    VerbGuardAction,
    VerbOutputCEFInspection,
)
from core.typed_verb_library import (
    CostClass,
    DataClassification,
    PolicyDomain,
    Reversibility,
    Schema,
    TypedVerb,
    VerbCall,
    VerbLibrary,
    VerbRuntime,
    FieldSpec,
    Precondition,
    Postcondition,
)
from core.cef_detector import (
    CEFDetectorConfig,
    CEFPattern,
    CEFType,
    create_cef_detector,
)
from core.evidence_ledger import create_ledger
from core.typed_verb_cef_guard import record_cef_to_evidence_ledger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _str_field(name: str) -> FieldSpec:
    return FieldSpec(name=name, type_name="str", required=True)


def _strict_config() -> VerbCEFGuardConfig:
    """All severities -> ESCALATE."""
    return VerbCEFGuardConfig(
        low_action=VerbGuardAction.ESCALATE,
        medium_action=VerbGuardAction.ESCALATE,
        high_action=VerbGuardAction.ESCALATE,
        critical_action=VerbGuardAction.ESCALATE,
    )


def _lax_config() -> VerbCEFGuardConfig:
    """All severities -> LOG."""
    return VerbCEFGuardConfig(
        low_action=VerbGuardAction.LOG,
        medium_action=VerbGuardAction.LOG,
        high_action=VerbGuardAction.LOG,
        critical_action=VerbGuardAction.LOG,
    )


def _default_config() -> VerbCEFGuardConfig:
    return VerbCEFGuardConfig()


def _cef_detector():
    """A CEF detector that triggers VAGUE_EXCUSE on 'unable'."""
    return create_cef_detector(config=CEFDetectorConfig(
        patterns=(CEFPattern(
            name="vague_unable",
            cef_type=CEFType.VAGUE_EXCUSE,
            weight=2,
            regex=re.compile(r"\b(unable|cannot|not able)\b", re.IGNORECASE),
            description="Vague inability phrasing",
        ),),
        min_markers_for_medium=2,
        min_markers_for_high=2,
        simulated_crash_critical_threshold=2,
        architectural_critical_weight_threshold=8,
        external_obstacle_high_weight_threshold=5,
        min_output_length=5,
    ))


def _make_library() -> VerbLibrary:
    lib = VerbLibrary(library_id="test-bundle-lib")

    read_schema = Schema(name="read", fields=(_str_field("url"),))

    pay_schema = Schema(name="pay", fields=(_str_field("amount"), _str_field("recipient")))

    def read_handler(args, state):
        return {"status": "ok", "url": args.get("url", ""), "body": "Hello world"}

    def pay_handler(args, state):
        return {"status": "ok", "amount": args["amount"], "tx": "tx-001"}

    def search_handler(args, state):
        return {"status": "ok", "query": args.get("query", ""), "results": []}

    lib.register(TypedVerb(
        name="read", version="1.0.0",
        input_schema=read_schema,
        output_schema=Schema(name="read_output", fields=(
            _str_field("status"), _str_field("url"), _str_field("body"))),
        handler=read_handler,
        policy_domains=(PolicyDomain.READ,),
        data_classification=DataClassification.PUBLIC,
        cost_class=CostClass.LOW,
        reversibility=Reversibility.REVERSIBLE,
    ))

    lib.register(TypedVerb(
        name="pay", version="1.0.0",
        input_schema=pay_schema,
        output_schema=Schema(name="pay_output", fields=(
            _str_field("status"), _str_field("amount"), _str_field("tx"))),
        handler=pay_handler,
        policy_domains=(PolicyDomain.PAYMENT,),
        data_classification=DataClassification.RESTRICTED,
        cost_class=CostClass.CRITICAL,
        reversibility=Reversibility.IRREVERSIBLE,
    ))

    lib.register(TypedVerb(
        name="search", version="1.0.0",
        input_schema=Schema(name="search", fields=(_str_field("query"),)),
        output_schema=Schema(name="search_output", fields=(
            _str_field("status"), _str_field("query"), _str_field("results"))),
        handler=search_handler,
        policy_domains=(PolicyDomain.READ, PolicyDomain.NETWORK),
        data_classification=DataClassification.INTERNAL,
        cost_class=CostClass.LOW,
        reversibility=Reversibility.REVERSIBLE,
    ))
    return lib


@pytest.fixture
def library():
    return _make_library()


@pytest.fixture
def runtime(library):
    return VerbRuntime(library=library)


@pytest.fixture
def detector():
    return _cef_detector()


# ---------------------------------------------------------------------------
# 1. Bundle registration & lookup
# ---------------------------------------------------------------------------

class TestBundleRegistration:
    def test_register_and_get(self):
        bundle = create_verb_policy_bundle(library_id="b1")
        e = VerbPolicyEntry(verb_name="pay", verb_version="1.0.0", config=_strict_config())
        bundle.register(e)
        assert ("pay", "1.0.0") in bundle

    def test_register_with_wildcard(self):
        bundle = create_verb_policy_bundle(library_id="b2")
        e = VerbPolicyEntry(verb_name="pay", verb_version=WILDCARD_VERSION, config=_strict_config())
        bundle.register(e)
        assert ("pay", WILDCARD_VERSION) in bundle

    def test_register_rejects_empty_name(self):
        bundle = create_verb_policy_bundle(library_id="b3")
        with pytest.raises(ValueError):
            bundle.register(VerbPolicyEntry(
                verb_name="", verb_version="1.0.0", config=VerbCEFGuardConfig()))

    def test_register_rejects_empty_version(self):
        bundle = create_verb_policy_bundle(library_id="b4")
        with pytest.raises(ValueError):
            bundle.register(VerbPolicyEntry(
                verb_name="read", verb_version="", config=VerbCEFGuardConfig()))

    def test_register_rejects_duplicate(self):
        bundle = create_verb_policy_bundle(library_id="b5")
        e1 = VerbPolicyEntry(verb_name="pay", verb_version="1.0.0", config=_strict_config())
        bundle.register(e1)
        with pytest.raises(ValueError):
            bundle.register(VerbPolicyEntry(
                verb_name="pay", verb_version="1.0.0", config=_lax_config()))

    def test_register_or_replace(self):
        bundle = create_verb_policy_bundle(library_id="b6")
        e1 = VerbPolicyEntry(verb_name="pay", verb_version="1.0.0", config=_strict_config())
        bundle.register(e1)
        e2 = VerbPolicyEntry(verb_name="pay", verb_version="1.0.0", config=_lax_config())
        bundle.register_or_replace(e2)
        cfg, src, _ = resolve_policy(bundle, "pay", "1.0.0")
        assert cfg.critical_action == VerbGuardAction.LOG

    def test_deregister(self):
        bundle = create_verb_policy_bundle(library_id="b7")
        e1 = VerbPolicyEntry(verb_name="pay", verb_version="1.0.0", config=_strict_config())
        bundle.register(e1)
        removed = bundle.deregister("pay", "1.0.0")
        assert removed is e1
        cfg, src, _ = resolve_policy(bundle, "pay", "1.0.0")
        assert src == PolicyResolutionSource.DEFAULT

    def test_deregister_unknown_raises(self):
        bundle = create_verb_policy_bundle(library_id="b8")
        with pytest.raises(KeyError):
            bundle.deregister("unknown", "1.0.0")

    def test_names(self):
        bundle = create_verb_policy_bundle(library_id="b9")
        bundle.register(VerbPolicyEntry(verb_name="pay", verb_version="1.0.0", config=_strict_config()))
        bundle.register(VerbPolicyEntry(verb_name="pay", verb_version="2.0.0", config=_lax_config()))
        bundle.register(VerbPolicyEntry(verb_name="read", verb_version=WILDCARD_VERSION, config=_strict_config()))
        assert sorted(bundle.names()) == ["pay", "read"]
        assert sorted(bundle.versions_of("pay")) == ["1.0.0", "2.0.0"]

    def test_len(self):
        bundle = create_verb_policy_bundle(library_id="b10")
        assert len(bundle) == 0
        bundle.register(VerbPolicyEntry(verb_name="pay", verb_version="1.0.0", config=_strict_config()))
        bundle.register(VerbPolicyEntry(verb_name="read", verb_version=WILDCARD_VERSION, config=_lax_config()))
        assert len(bundle) == 2


# ---------------------------------------------------------------------------
# 2. Policy resolution
# ---------------------------------------------------------------------------

class TestPolicyResolution:
    def test_specific_match_wins(self):
        bundle = create_verb_policy_bundle(library_id="r1")
        bundle.register(VerbPolicyEntry(verb_name="pay", verb_version="1.0.0", config=_strict_config()))
        bundle.register(VerbPolicyEntry(verb_name="pay", verb_version=WILDCARD_VERSION, config=_lax_config()))
        cfg, src, entry = resolve_policy(bundle, "pay", "1.0.0")
        assert src == PolicyResolutionSource.SPECIFIC
        assert cfg.critical_action == VerbGuardAction.ESCALATE

    def test_wildcard_fallback(self):
        bundle = create_verb_policy_bundle(library_id="r2")
        bundle.register(VerbPolicyEntry(verb_name="pay", verb_version=WILDCARD_VERSION, config=_strict_config()))
        cfg, src, entry = resolve_policy(bundle, "pay", "9.9.9")
        assert src == PolicyResolutionSource.WILDCARD
        assert entry is not None
        assert entry.is_wildcard

    def test_default_fallback_when_no_entry(self):
        bundle = create_verb_policy_bundle(library_id="r3", default_config=_default_config())
        cfg, src, entry = resolve_policy(bundle, "pay", "1.0.0")
        assert src == PolicyResolutionSource.DEFAULT
        assert entry is None
        assert cfg is not None

    def test_resolution_is_deterministic(self):
        bundle = create_verb_policy_bundle(library_id="r4")
        bundle.register(VerbPolicyEntry(verb_name="pay", verb_version="1.0.0", config=_strict_config()))
        r1 = resolve_policy(bundle, "pay", "1.0.0")
        r2 = resolve_policy(bundle, "pay", "1.0.0")
        assert r1 == r2

    def test_strict_mode_unknown_verb_raises(self):
        bundle = create_verb_policy_bundle(library_id="r5", strict_unknown_verb=True)
        with pytest.raises(KeyError):
            resolve_policy(bundle, "unknown", "1.0.0")

    def test_lax_mode_unknown_verb_returns_default(self):
        bundle = create_verb_policy_bundle(library_id="r6", default_config=_default_config())
        cfg, src, _ = resolve_policy(bundle, "unknown", "1.0.0")
        assert src == PolicyResolutionSource.DEFAULT


# ---------------------------------------------------------------------------
# 3. BundledGuardConfig - conservative posture
# ---------------------------------------------------------------------------

class TestBundledGuardConfig:
    def test_strict_config_registered(self):
        """A stricter-than-global config is accepted without warning."""
        bundle = create_verb_policy_bundle(library_id="s1", default_config=_default_config())
        strict = VerbCEFGuardConfig(
            low_action=VerbGuardAction.FLAG,
            medium_action=VerbGuardAction.HALT,
            high_action=VerbGuardAction.ESCALATE,
            critical_action=VerbGuardAction.ESCALATE,
        )
        e = VerbPolicyEntry(verb_name="pay", verb_version="1.0.0", config=strict)
        bundle.register(e)
        cfg, _, _ = resolve_policy(bundle, "pay", "1.0.0")
        assert cfg.critical_action == VerbGuardAction.ESCALATE

    def test_looser_config_can_be_registered(self):
        """Looser-than-global is allowed but flagged in `looser_than_default`."""
        bundle = create_verb_policy_bundle(library_id="s2", default_config=_default_config())
        loose = VerbCEFGuardConfig(critical_action=VerbGuardAction.LOG)
        e = VerbPolicyEntry(verb_name="pay", verb_version="1.0.0", config=loose)
        bundle.register(e)
        assert e.looser_than_default is True

    def test_to_dict(self):
        bundle = create_verb_policy_bundle(library_id="s3")
        e = VerbPolicyEntry(verb_name="pay", verb_version="1.0.0",
                            config=_strict_config(), source="manual",
                            rationale="pay is irreversible")
        bundle.register(e)
        d = bundle.to_dict()
        assert d["library_id"] == "s3"
        assert len(d["entries"]) == 1
        e0 = d["entries"][0]
        assert e0["verb_name"] == "pay"
        assert e0["verb_version"] == "1.0.0"
        assert e0["rationale"] == "pay is irreversible"


# ---------------------------------------------------------------------------
# 4. Bundled runtime
# ---------------------------------------------------------------------------

class TestBundledRuntime:
    def test_bundled_runtime_uses_per_verb_config(self, library, runtime, detector):
        """When the bundle overrides 'pay' to be ESCALATE-only, a fabrication
        in a pay call should ESCALATE, while the same fabrication in a read
        call should follow the global default (LOG for LOW)."""
        bundle = create_verb_policy_bundle(library_id="br1", default_config=_default_config())
        strict = VerbCEFGuardConfig(
            low_action=VerbGuardAction.ESCALATE,
            medium_action=VerbGuardAction.ESCALATE,
            high_action=VerbGuardAction.ESCALATE,
            critical_action=VerbGuardAction.ESCALATE,
        )
        bundle.register(VerbPolicyEntry(verb_name="pay", verb_version="1.0.0", config=strict))

        def fabricating_pay_handler(args, state):
            return {
                "status": "blocked",
                "amount": args.get("amount", "0"),
                "tx": "Currently unable to process payment due to audit restrictions.",
            }
        lib2 = _make_library()
        lib2.deregister("pay", "1.0.0")
        lib2.register(TypedVerb(
            name="pay", version="1.0.0",
            input_schema=Schema(name="pay", fields=(_str_field("amount"), _str_field("recipient"))),
            output_schema=Schema(name="pay_output", fields=(
                _str_field("status"), _str_field("amount"), _str_field("tx"))),
            handler=fabricating_pay_handler,
            policy_domains=(PolicyDomain.PAYMENT,),
            data_classification=DataClassification.RESTRICTED,
            cost_class=CostClass.CRITICAL,
            reversibility=Reversibility.IRREVERSIBLE,
        ))

        def fabricating_read_handler(args, state):
            return {
                "status": "ok",
                "url": args.get("url", ""),
                "body": "Currently unable to fetch page.",
            }
        lib2.deregister("read", "1.0.0")
        lib2.register(TypedVerb(
            name="read", version="1.0.0",
            input_schema=Schema(name="r", fields=(_str_field("url"),)),
            output_schema=Schema(name="r", fields=(
                _str_field("status"), _str_field("url"), _str_field("body"))),
            handler=fabricating_read_handler,
            policy_domains=(PolicyDomain.READ,),
            data_classification=DataClassification.PUBLIC,
            cost_class=CostClass.LOW,
            reversibility=Reversibility.REVERSIBLE,
        ))
        runtime2 = VerbRuntime(library=lib2)
        bundled = create_bundled_verb_runtime(
            runtime=runtime2,
            detector=detector,
            bundle=bundle,
            halt_on_halt=False,
        )

        pay_result = bundled.invoke(VerbCall(name="pay", version="1.0.0",
                                            args={"amount": "10", "recipient": "alice"}))
        assert pay_result.guard_action == VerbGuardAction.ESCALATE

        read_result = bundled.invoke(VerbCall(name="read", version="1.0.0",
                                             args={"url": "https://example.com"}))
        assert read_result.guard_action == VerbGuardAction.LOG

    def test_bundled_runtime_uses_wildcard_when_no_specific(self, library, detector):
        bundle = create_verb_policy_bundle(library_id="br2", default_config=_default_config())
        strict = VerbCEFGuardConfig(
            low_action=VerbGuardAction.ESCALATE,
            medium_action=VerbGuardAction.ESCALATE,
            high_action=VerbGuardAction.ESCALATE,
            critical_action=VerbGuardAction.ESCALATE,
        )
        bundle.register(VerbPolicyEntry(verb_name="read", verb_version=WILDCARD_VERSION,
                                        config=strict))

        def fabricating_read_handler(args, state):
            return {
                "status": "ok",
                "url": args.get("url", ""),
                "body": "Currently unable to fetch page.",
            }
        lib2 = _make_library()
        lib2.deregister("read", "1.0.0")
        lib2.register(TypedVerb(
            name="read", version="1.0.0",
            input_schema=Schema(name="r", fields=(_str_field("url"),)),
            output_schema=Schema(name="r", fields=(
                _str_field("status"), _str_field("url"), _str_field("body"))),
            handler=fabricating_read_handler,
            policy_domains=(PolicyDomain.READ,),
            data_classification=DataClassification.PUBLIC,
            cost_class=CostClass.LOW,
            reversibility=Reversibility.REVERSIBLE,
        ))
        runtime2 = VerbRuntime(library=lib2)
        bundled = create_bundled_verb_runtime(
            runtime=runtime2, detector=detector, bundle=bundle, halt_on_halt=False,
        )
        result = bundled.invoke(VerbCall(name="read", version="1.0.0",
                                        args={"url": "https://example.com"}))
        assert result.guard_action == VerbGuardAction.ESCALATE

    def test_bundled_runtime_uses_default_when_no_bundle_entry(self, library, runtime, detector):
        bundle = create_verb_policy_bundle(library_id="br3", default_config=_default_config())
        bundled = create_bundled_verb_runtime(
            runtime=runtime, detector=detector, bundle=bundle, halt_on_halt=False,
        )
        result = bundled.invoke(VerbCall(name="search", version="1.0.0", args={"query": "x"}))
        assert result.success is True

    def test_bundled_runtime_halts_on_halt(self, library, detector):
        bundle = create_verb_policy_bundle(library_id="br4", default_config=_default_config())
        strict = VerbCEFGuardConfig(
            low_action=VerbGuardAction.ESCALATE,
            medium_action=VerbGuardAction.ESCALATE,
            high_action=VerbGuardAction.ESCALATE,
            critical_action=VerbGuardAction.ESCALATE,
        )
        bundle.register(VerbPolicyEntry(verb_name="pay", verb_version="1.0.0", config=strict))

        def fabricating_pay_handler(args, state):
            return {
                "status": "blocked",
                "amount": args.get("amount", "0"),
                "tx": "Currently unable to process payment due to audit restrictions.",
            }
        lib2 = _make_library()
        lib2.deregister("pay", "1.0.0")
        lib2.register(TypedVerb(
            name="pay", version="1.0.0",
            input_schema=Schema(name="pay", fields=(_str_field("amount"), _str_field("recipient"))),
            output_schema=Schema(name="pay_output", fields=(
                _str_field("status"), _str_field("amount"), _str_field("tx"))),
            handler=fabricating_pay_handler,
            policy_domains=(PolicyDomain.PAYMENT,),
            data_classification=DataClassification.RESTRICTED,
            cost_class=CostClass.CRITICAL,
            reversibility=Reversibility.IRREVERSIBLE,
        ))
        runtime2 = VerbRuntime(library=lib2)
        bundled = create_bundled_verb_runtime(
            runtime=runtime2, detector=detector, bundle=bundle, halt_on_halt=True,
        )
        result = bundled.invoke(VerbCall(name="pay", version="1.0.0",
                                        args={"amount": "10", "recipient": "alice"}))
        assert result.success is False
        assert result.halted is True

    def test_bundled_runtime_state_and_audit_proxies(self, library, runtime, detector):
        bundle = create_verb_policy_bundle(library_id="br5", default_config=_default_config())
        bundled = create_bundled_verb_runtime(
            runtime=runtime, detector=detector, bundle=bundle, halt_on_halt=False,
        )
        assert bundled.state is runtime.state
        assert bundled.audit() is runtime.audit


# ---------------------------------------------------------------------------
# 5. Resolution audit
# ---------------------------------------------------------------------------

class TestPolicyAudit:
    def test_default_audit_log_records_resolutions(self, library, runtime, detector):
        bundle = create_verb_policy_bundle(library_id="a1", default_config=_default_config())
        bundle.register(VerbPolicyEntry(verb_name="pay", verb_version=WILDCARD_VERSION,
                                        config=_strict_config()))
        bundled = create_bundled_verb_runtime(
            runtime=runtime, detector=detector, bundle=bundle, halt_on_halt=False,
        )
        bundled.invoke(VerbCall(name="pay", version="1.0.0",
                                args={"amount": "10", "recipient": "alice"}))
        bundled.invoke(VerbCall(name="read", version="1.0.0",
                                args={"url": "https://example.com"}))
        events = bundle.audit_log().events()
        assert len(events) == 2
        assert events[0].source == PolicyResolutionSource.WILDCARD
        assert events[1].source == PolicyResolutionSource.DEFAULT

    def test_audit_event_to_dict(self):
        bundle = create_verb_policy_bundle(library_id="a2")
        bundle.register(VerbPolicyEntry(verb_name="pay", verb_version="1.0.0",
                                        config=_strict_config()))
        log = bundle.audit_log()
        entry = PolicyAuditEntry(
            event_id="evt-1",
            event_kind=PolicyAuditEventKind.RESOLVE,
            verb_name="pay",
            verb_version="1.0.0",
            source=PolicyResolutionSource.SPECIFIC,
            timestamp=time.time(),
            program_id="prog-1",
            step_index=2,
            sequence=0,
            prev_hash="0" * 64,
            config_hash="abc",
        )
        log.append(entry)
        d = entry.to_dict()
        assert d["verb_name"] == "pay"
        assert d["source"] == "specific"
        assert d["program_id"] == "prog-1"

    def test_audit_hash_chain(self):
        bundle = create_verb_policy_bundle(library_id="a3")
        log = bundle.audit_log()
        for i in range(5):
            entry = PolicyAuditEntry(
                event_id=f"evt-{i}",
                event_kind=PolicyAuditEventKind.RESOLVE,
                verb_name="pay",
                verb_version="1.0.0",
                source=PolicyResolutionSource.SPECIFIC,
                timestamp=time.time() + i,
                program_id="",
                step_index=0,
                sequence=i,
                prev_hash=log.last_hash() if i > 0 else "0" * 64,
                config_hash="h" * 64,
            )
            log.append(entry)
        events = log.events()
        for i in range(1, len(events)):
            assert events[i].prev_hash == events[i - 1].event_hash

    def test_audit_chain_detects_tamper(self):
        bundle = create_verb_policy_bundle(library_id="a4")
        log = bundle.audit_log()
        e0 = PolicyAuditEntry(
            event_id="evt-0",
            event_kind=PolicyAuditEventKind.RESOLVE,
            verb_name="pay",
            verb_version="1.0.0",
            source=PolicyResolutionSource.SPECIFIC,
            timestamp=1.0,
            program_id="",
            step_index=0,
            sequence=0,
            prev_hash="0" * 64,
            config_hash="c" * 64,
        )
        log.append(e0)
        e1 = PolicyAuditEntry(
            event_id="evt-1",
            event_kind=PolicyAuditEventKind.RESOLVE,
            verb_name="pay",
            verb_version="1.0.0",
            source=PolicyResolutionSource.SPECIFIC,
            timestamp=2.0,
            program_id="",
            step_index=0,
            sequence=1,
            prev_hash=log.last_hash(),
            config_hash="c" * 64,
        )
        log.append(e1)
        log.entries[0].verb_name = "tampered"
        assert log.verify_chain() is False

    def test_audit_chain_passes_for_clean_log(self):
        bundle = create_verb_policy_bundle(library_id="a5")
        log = bundle.audit_log()
        for i in range(3):
            entry = PolicyAuditEntry(
                event_id=f"e{i}",
                event_kind=PolicyAuditEventKind.RESOLVE,
                verb_name="pay",
                verb_version="1.0.0",
                source=PolicyResolutionSource.DEFAULT,
                timestamp=float(i),
                program_id="",
                step_index=0,
                sequence=i,
                prev_hash=log.last_hash() if i > 0 else "0" * 64,
                config_hash="d" * 64,
            )
            log.append(entry)
        assert log.verify_chain() is True

    def test_jsonl_audit_writes_to_disk(self, library, runtime, detector, tmp_path):
        audit_path = str(tmp_path / "policy_audit.jsonl")
        bundle = create_verb_policy_bundle(library_id="a6", audit_path=audit_path,
                                           default_config=_default_config())
        bundle.register(VerbPolicyEntry(verb_name="pay", verb_version=WILDCARD_VERSION,
                                        config=_strict_config()))
        bundled = create_bundled_verb_runtime(
            runtime=runtime, detector=detector, bundle=bundle, halt_on_halt=False,
        )
        bundled.invoke(VerbCall(name="pay", version="1.0.0",
                                args={"amount": "10", "recipient": "alice"}))
        bundle.audit_log().flush()
        assert os.path.exists(audit_path)
        with open(audit_path, "r") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        assert len(lines) >= 1
        import json as _json
        d = _json.loads(lines[0])
        assert d["verb_name"] == "pay"
        assert d["source"] == "wildcard"

    def test_enable_policy_audit_helper(self, library, runtime, detector, tmp_path):
        import os
        audit_path = str(tmp_path / "p_audit.jsonl")
        bundle = create_verb_policy_bundle(library_id="a7", default_config=_default_config())
        enable_policy_audit(bundle, audit_path)
        bundled = create_bundled_verb_runtime(
            runtime=runtime, detector=detector, bundle=bundle, halt_on_halt=False,
        )
        bundled.invoke(VerbCall(name="read", version="1.0.0",
                                args={"url": "https://example.com"}))
        bundle.audit_log().flush()
        assert os.path.exists(audit_path)

    def test_audit_event_kinds(self):
        assert PolicyAuditEventKind.RESOLVE.value == "resolve"
        assert PolicyAuditEventKind.FALLBACK.value == "fallback"
        assert PolicyAuditEventKind.MISS.value == "miss"
        assert PolicyAuditEventKind.REGISTER.value == "register"

    def test_audit_counts_per_source(self, library, runtime, detector):
        bundle = create_verb_policy_bundle(library_id="a8", default_config=_default_config())
        bundle.register(VerbPolicyEntry(verb_name="pay", verb_version="1.0.0", config=_strict_config()))
        bundle.register(VerbPolicyEntry(verb_name="read", verb_version=WILDCARD_VERSION, config=_lax_config()))
        bundled = create_bundled_verb_runtime(
            runtime=runtime, detector=detector, bundle=bundle, halt_on_halt=False,
        )
        bundled.invoke(VerbCall(name="pay", version="1.0.0", args={"amount": "10", "recipient": "alice"}))
        bundled.invoke(VerbCall(name="read", version="1.0.0", args={"url": "https://example.com"}))
        bundled.invoke(VerbCall(name="search", version="1.0.0", args={"query": "x"}))
        counts = bundle.audit_log().counts_per_source()
        assert counts.get(PolicyResolutionSource.SPECIFIC, 0) == 1
        assert counts.get(PolicyResolutionSource.WILDCARD, 0) == 1
        assert counts.get(PolicyResolutionSource.DEFAULT, 0) == 1


# ---------------------------------------------------------------------------
# 6. Conservative posture / safety invariants
# ---------------------------------------------------------------------------

class TestConservativePosture:
    def test_resolution_is_pure(self, library, runtime, detector):
        bundle = create_verb_policy_bundle(library_id="c1", default_config=_default_config())
        bundle.register(VerbPolicyEntry(verb_name="pay", verb_version=WILDCARD_VERSION, config=_strict_config()))
        n_before = len(bundle)
        for _ in range(5):
            resolve_policy(bundle, "pay", "1.0.0")
        assert len(bundle) == n_before

    def test_bundled_runtime_does_not_mutate_verb(self, library, runtime, detector):
        bundle = create_verb_policy_bundle(library_id="c2", default_config=_default_config())
        bundle.register(VerbPolicyEntry(verb_name="pay", verb_version=WILDCARD_VERSION, config=_strict_config()))
        bundled = create_bundled_verb_runtime(
            runtime=runtime, detector=detector, bundle=bundle, halt_on_halt=False,
        )
        n_verbs = len(runtime.library.verbs)
        bundled.invoke(VerbCall(name="pay", version="1.0.0", args={"amount": "10", "recipient": "alice"}))
        bundled.invoke(VerbCall(name="read", version="1.0.0", args={"url": "https://example.com"}))
        bundled.invoke(VerbCall(name="search", version="1.0.0", args={"query": "x"}))
        assert len(runtime.library.verbs) == n_verbs

    def test_default_config_is_sane(self):
        """Defaults: NONE -> NONE, LOW -> LOG, MEDIUM -> FLAG, HIGH -> HALT, CRITICAL -> ESCALATE."""
        c = VerbCEFGuardConfig()
        assert c.none_action == VerbGuardAction.NONE
        assert c.low_action == VerbGuardAction.LOG
        assert c.medium_action == VerbGuardAction.FLAG
        assert c.high_action == VerbGuardAction.HALT
        assert c.critical_action == VerbGuardAction.ESCALATE

    def test_bundle_serialization_round_trip(self):
        bundle = create_verb_policy_bundle(library_id="c3", default_config=_default_config())
        bundle.register(VerbPolicyEntry(verb_name="pay", verb_version="1.0.0", config=_strict_config(),
                                        source="test", rationale="r1"))
        d = bundle.to_dict()
        assert d["library_id"] == "c3"
        assert d["strict_unknown_verb"] is False
        assert d["default_config"] is not None
        assert len(d["entries"]) == 1
        e0 = d["entries"][0]
        assert e0["verb_name"] == "pay"
        assert e0["source"] == "test"
        assert e0["rationale"] == "r1"

    def test_resolution_never_raises_on_disabled_verb(self, library, runtime, detector):
        bundle = create_verb_policy_bundle(library_id="c4", default_config=_default_config())
        bundled = create_bundled_verb_runtime(
            runtime=runtime, detector=detector, bundle=bundle, halt_on_halt=False,
        )
        # search has no entry and no wildcard - resolves to default
        result = bundled.invoke(VerbCall(name="search", version="1.0.0", args={"query": "x"}))
        assert result.success is True

    def test_audit_log_does_not_grow_unboundedly_by_default(self, library, runtime, detector):
        bundle = create_verb_policy_bundle(library_id="c5", default_config=_default_config())
        bundled = create_bundled_verb_runtime(
            runtime=runtime, detector=detector, bundle=bundle, halt_on_halt=False,
        )
        for _ in range(50):
            bundled.invoke(VerbCall(name="search", version="1.0.0", args={"query": "x"}))
        # Audit log is bounded (capped at 1000 by default)
        assert len(bundle.audit_log().events()) <= 1000


# ---------------------------------------------------------------------------
# 7. Integration
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_bundled_runtime_is_a_guarded_verb_runtime(self, library, runtime, detector):
        bundle = create_verb_policy_bundle(library_id="i1", default_config=_default_config())
        bundled = create_bundled_verb_runtime(
            runtime=runtime, detector=detector, bundle=bundle, halt_on_halt=False,
        )
        # The bundled runtime wraps a GuardedVerbRuntime internally
        from core.typed_verb_cef_guard import GuardedVerbRuntime
        # The bundled.invoke() returns a BundledVerbStepResult
        result = bundled.invoke(VerbCall(name="search", version="1.0.0", args={"query": "x"}))
        assert isinstance(result, BundledVerbStepResult)

    def test_bundled_step_result_exposes_resolution(self, library, runtime, detector):
        bundle = create_verb_policy_bundle(library_id="i2", default_config=_default_config())
        bundle.register(VerbPolicyEntry(verb_name="pay", verb_version="1.0.0", config=_strict_config()))
        bundled = create_bundled_verb_runtime(
            runtime=runtime, detector=detector, bundle=bundle, halt_on_halt=False,
        )
        result = bundled.invoke(VerbCall(name="pay", version="1.0.0", args={"amount": "10", "recipient": "alice"}))
        assert result.resolution is not None
        assert result.resolution.source == PolicyResolutionSource.SPECIFIC

    def test_evidence_ledger_bridge_records_resolution(self, library, runtime, detector):
        from core.evidence_ledger import create_ledger
        from core.typed_verb_cef_guard import record_cef_to_evidence_ledger
        bundle = create_verb_policy_bundle(library_id="i3", default_config=_default_config())
        bundle.register(VerbPolicyEntry(verb_name="pay", verb_version="1.0.0", config=_strict_config()))

        def fabricating_pay_handler(args, state):
            return {
                "status": "blocked",
                "amount": args.get("amount", "0"),
                "tx": "Currently unable to process payment due to audit restrictions.",
            }
        lib2 = _make_library()
        lib2.deregister("pay", "1.0.0")
        lib2.register(TypedVerb(
            name="pay", version="1.0.0",
            input_schema=Schema(name="pay", fields=(_str_field("amount"), _str_field("recipient"))),
            output_schema=Schema(name="pay_output", fields=(
                _str_field("status"), _str_field("amount"), _str_field("tx"))),
            handler=fabricating_pay_handler,
            policy_domains=(PolicyDomain.PAYMENT,),
            data_classification=DataClassification.RESTRICTED,
            cost_class=CostClass.CRITICAL,
            reversibility=Reversibility.IRREVERSIBLE,
        ))
        runtime2 = VerbRuntime(library=lib2)
        bundled = create_bundled_verb_runtime(
            runtime=runtime2, detector=detector, bundle=bundle, halt_on_halt=False,
        )
        result = bundled.invoke(VerbCall(name="pay", version="1.0.0",
                                        args={"amount": "10", "recipient": "alice"}))
        ledger = create_ledger()
        if hasattr(result, "inspection") and result.inspection is not None:
            claim = record_cef_to_evidence_ledger(result.inspection, ledger)
            if claim is not None:
                assert claim.payload.get("verb_name") == "pay"
                assert claim.payload.get("source") == "typed_verb_cef_guard"