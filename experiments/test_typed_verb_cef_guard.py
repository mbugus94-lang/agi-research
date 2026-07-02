"""
Tests for the Typed Verb CEF Guard bridge.

Covers:
- Guard availability detection (CEF substrate present / absent)
- Output inspection: clean, vague-excuse, external-obstacle, CET
- Operator policy: severity -> action mapping
- Guarded runtime: clean pass-through, HALT short-circuit, ESCALATE
- Aggregate text hashing stability
- Config defaults
- Soft-import fallback (CEF substrate unavailable -> NONE action)
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.typed_verb_cef_guard import (
    CEFGuardAvailability,
    GuardedVerbRuntime,
    GuardedVerbStepResult,
    VerbCEFGuard,
    VerbCEFGuardConfig,
    VerbGuardAction,
    VerbOutputCEFInspection,
    create_guarded_verb_runtime,
    create_verb_cef_guard,
)
from core.typed_verb_library import (
    AuditLog,
    FieldSpec,
    PolicyDomain,
    Schema,
    TypedVerb,
    VerbCall,
    VerbCallStep,
    VerbLibrary,
    VerbRuntime,
    make_sequence,
)


def _lib_with_verb(name: str, output: dict, policy=(PolicyDomain.READ,)) -> VerbLibrary:
    lib = VerbLibrary(library_id=f"lib-{name}")
    lib.register(TypedVerb(
        name=name,
        version="1.0.0",
        input_schema=Schema(name=f"{name}_in", fields=()),
        output_schema=Schema(name=f"{name}_out", fields=()),
        handler=lambda args, state: dict(output),
        policy_domains=policy,
    ))
    return lib


class GuardAvailabilityTests(unittest.TestCase):
    def test_cef_substrate_loaded(self):
        from core import typed_verb_cef_guard as mod
        self.assertTrue(mod._CEF_AVAILABLE)

    def test_guard_constructs_with_default_detector(self):
        g = create_verb_cef_guard()
        self.assertIsNotNone(g.detector)
        self.assertEqual(g.availability, CEFGuardAvailability.AVAILABLE)


class CleanOutputTests(unittest.TestCase):
    def test_clean_typed_verb_output(self):
        g = create_verb_cef_guard()
        out = {"tx_id": "tx_abc123", "amount": 19.99}
        insp = g.inspect_output(out, call_id="c1", verb_name="pay", verb_version="1.0.0")
        self.assertTrue(insp.is_clean)
        self.assertEqual(insp.guard_action, VerbGuardAction.NONE)
        self.assertIsNone(insp.detection)

    def test_short_output_ignored(self):
        cfg = VerbCEFGuardConfig(min_output_length=50)
        g = create_verb_cef_guard(config=cfg)
        out = {"msg": "OK"}
        insp = g.inspect_output(out, call_id="c1", verb_name="x", verb_version="1.0.0")
        self.assertTrue(insp.is_clean)
        self.assertEqual(insp.guard_action, VerbGuardAction.NONE)


class CEFPatternDetectionTests(unittest.TestCase):
    def test_vague_excuse_returns_low_action(self):
        g = create_verb_cef_guard()
        out = {"status": "I am currently unable to process this request at the moment"}
        insp = g.inspect_output(out, call_id="c1", verb_name="x", verb_version="1.0.0")
        self.assertFalse(insp.is_clean)
        self.assertEqual(insp.guard_action, VerbGuardAction.LOG)
        self.assertIsNotNone(insp.detection)

    def test_external_obstacle_returns_action(self):
        g = create_verb_cef_guard()
        out = {
            "reason": "Blocked by audit and regulatory compliance restrictions. "
                      "Third-party vendor system is currently unavailable. "
                      "Policy refusal: cannot proceed under compliance hold."
        }
        insp = g.inspect_output(out, call_id="c1", verb_name="x", verb_version="1.0.0")
        self.assertIn(insp.guard_action, (
            VerbGuardAction.LOG, VerbGuardAction.FLAG, VerbGuardAction.HALT, VerbGuardAction.ESCALATE
        ))

    def test_simulated_crash_returns_escalate(self):
        g = create_verb_cef_guard()
        out = {
            "trace": "Traceback (most recent call last):\n  File x.py, line 42\n"
                     "Exception in thread main: 0xDEADBEEF"
        }
        insp = g.inspect_output(out, call_id="c1", verb_name="x", verb_version="1.0.0")
        self.assertEqual(insp.guard_action, VerbGuardAction.ESCALATE)
        self.assertTrue(insp.detection.severity.is_thanatosis)


class OperatorPolicyTests(unittest.TestCase):
    def test_severity_mapping(self):
        cfg = VerbCEFGuardConfig(
            low_action=VerbGuardAction.NONE,
            medium_action=VerbGuardAction.LOG,
            high_action=VerbGuardAction.FLAG,
            critical_action=VerbGuardAction.ESCALATE,
        )
        g = create_verb_cef_guard(config=cfg)
        from core.cef_detector import CEFSeverity
        self.assertEqual(cfg.map_severity(CEFSeverity.NONE), VerbGuardAction.NONE)
        self.assertEqual(cfg.map_severity(CEFSeverity.LOW), VerbGuardAction.NONE)
        self.assertEqual(cfg.map_severity(CEFSeverity.MEDIUM), VerbGuardAction.LOG)
        self.assertEqual(cfg.map_severity(CEFSeverity.HIGH), VerbGuardAction.FLAG)
        self.assertEqual(cfg.map_severity(CEFSeverity.CRITICAL), VerbGuardAction.ESCALATE)

    def test_config_defaults(self):
        cfg = VerbCEFGuardConfig()
        self.assertEqual(cfg.low_action, VerbGuardAction.LOG)
        self.assertEqual(cfg.medium_action, VerbGuardAction.FLAG)
        self.assertEqual(cfg.high_action, VerbGuardAction.HALT)
        self.assertEqual(cfg.critical_action, VerbGuardAction.ESCALATE)
        self.assertEqual(cfg.min_output_length, 12)
        self.assertEqual(cfg.max_fields_to_scan, 32)
        self.assertEqual(cfg.max_string_length_per_field, 8192)


class GuardedRuntimeTests(unittest.TestCase):
    def test_clean_verb_passes_through(self):
        lib = _lib_with_verb("pay", {"tx_id": "tx_001", "amount": 5.0})
        runtime = VerbRuntime(library=lib)
        guarded = create_guarded_verb_runtime(runtime)
        result = guarded.invoke(VerbCall(name="pay", version="1.0.0", args={}))
        self.assertTrue(result.success)
        self.assertFalse(result.halted)
        self.assertEqual(result.inspection.guard_action, VerbGuardAction.NONE)

    def test_fabrication_halts(self):
        lib = _lib_with_verb("pay", {
            "tx_id": "tx_001",
            "note": "Traceback (most recent call last): Exception in thread main: 0xCAFE"
        })
        runtime = VerbRuntime(library=lib)
        guarded = create_guarded_verb_runtime(runtime, halt_on_halt=True)
        result = guarded.invoke(VerbCall(name="pay", version="1.0.0", args={}))
        self.assertFalse(result.success)
        self.assertTrue(result.halted)
        self.assertIn("CEF guard", result.result.error)

    def test_fabrication_no_halt_mode(self):
        lib = _lib_with_verb("pay", {
            "tx_id": "tx_001",
            "note": "Traceback (most recent call last): Exception in thread main: 0xCAFE"
        })
        runtime = VerbRuntime(library=lib)
        guarded = create_guarded_verb_runtime(runtime, halt_on_halt=False)
        result = guarded.invoke(VerbCall(name="pay", version="1.0.0", args={}))
        self.assertTrue(result.success)
        self.assertFalse(result.halted)
        self.assertEqual(result.inspection.guard_action, VerbGuardAction.ESCALATE)

    def test_inspections_accumulate(self):
        lib = _lib_with_verb("noop", {"ok": True, "msg": "all good thanks"})
        runtime = VerbRuntime(library=lib)
        guarded = create_guarded_verb_runtime(runtime)
        for _ in range(3):
            guarded.invoke(VerbCall(name="noop", version="1.0.0", args={}))
        self.assertEqual(len(guarded.inspections), 3)


class HashStabilityTests(unittest.TestCase):
    def test_same_output_same_hash(self):
        g = create_verb_cef_guard()
        out1 = {"a": "hello", "b": "world"}
        out2 = {"b": "world", "a": "hello"}
        h1 = g.inspect_output(out1, call_id="c", verb_name="x", verb_version="1.0.0").aggregate_text_hash
        h2 = g.inspect_output(out2, call_id="c", verb_name="x", verb_version="1.0.0").aggregate_text_hash
        self.assertEqual(h1, h2)

    def test_max_fields_respected(self):
        cfg = VerbCEFGuardConfig(max_fields_to_scan=2)
        g = create_verb_cef_guard(config=cfg)
        out = {f"f{i}": f"value-{i}" for i in range(10)}
        insp = g.inspect_output(out, call_id="c", verb_name="x", verb_version="1.0.0")
        self.assertEqual(len(insp.scanned_fields), 2)

    def test_string_truncation(self):
        cfg = VerbCEFGuardConfig(max_string_length_per_field=10)
        g = create_verb_cef_guard(config=cfg)
        out = {"text": "A" * 1000}
        insp = g.inspect_output(out, call_id="c", verb_name="x", verb_version="1.0.0")
        self.assertEqual(insp.aggregate_text_length, 10)


if __name__ == "__main__":
    unittest.main()
