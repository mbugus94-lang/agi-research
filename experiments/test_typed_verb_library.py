"""
Tests for the Typed Verb Library (Web-Verb Layer).

Covers:
- Verb registration and lookup
- Static checking of program steps
- Runtime execution for sequence / conditional steps
- Precondition and postcondition enforcement
- Append-only hash-chained audit log
- Conservative policy gating
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.typed_verb_library import (
    AuditLog,
    CheckVerdict,
    ConditionalStep,
    CostClass,
    DataClassification,
    FieldSpec,
    PolicyDomain,
    Postcondition,
    Precondition,
    Reversibility,
    Schema,
    SequenceStep,
    StepKind,
    TypedVerb,
    VerbCall,
    VerbCallStep,
    VerbLibrary,
    VerbRuntime,
    collect_verb_calls,
    create_typed_verb_runtime,
    execute_program,
    make_conditional,
    make_sequence,
    static_check,
)


def _verb_library() -> VerbLibrary:
    lib = VerbLibrary(library_id="test-lib")

    def _flag_present(state, args):
        return bool(state.get("flag") or args.get("flag"))

    def _out_ok(state, args):
        return bool(args.get("_last_output", {}).get("ok"))

    lib.register(
        TypedVerb(
            name="hello",
            version="1.0.0",
            description="Say hello",
            input_schema=Schema(
                name="hello_input",
                fields=(FieldSpec(name="name", type_name="string", required=True),),
            ),
            output_schema=Schema(
                name="hello_output",
                fields=(FieldSpec(name="ok", type_name="boolean", required=True),),
            ),
            handler=lambda args, state: {"ok": True, "greeting": f"hi {args['name']}"},
            preconditions=(Precondition(name="flag_present", predicate=_flag_present),),
            postconditions=(Postcondition(name="ok_output", predicate=_out_ok),),
            policy_domains=(PolicyDomain.READ,),
            data_classification=DataClassification.PUBLIC,
            cost_class=CostClass.LOW,
            reversibility=Reversibility.REVERSIBLE,
        )
    )

    lib.register(
        TypedVerb(
            name="write_note",
            version="1.0.0",
            description="Write a note",
            input_schema=Schema(
                name="write_input",
                fields=(FieldSpec(name="text", type_name="string", required=True),),
            ),
            output_schema=Schema(
                name="write_output",
                fields=(FieldSpec(name="written", type_name="boolean", required=True),),
            ),
            handler=lambda args, state: {"written": True},
            policy_domains=(PolicyDomain.WRITE,),
            data_classification=DataClassification.INTERNAL,
            cost_class=CostClass.MEDIUM,
            reversibility=Reversibility.DEGRADED,
        )
    )

    return lib


class TypedVerbLibraryTests(unittest.TestCase):
    def test_register_and_lookup(self):
        lib = _verb_library()
        self.assertEqual(len(lib), 2)
        self.assertIn("hello", lib)
        self.assertEqual(lib.get("hello").name, "hello")
        self.assertEqual(lib.names(), ["hello", "write_note"])

    def test_static_check_passes(self):
        lib = _verb_library()
        program = make_sequence(
            VerbCallStep(call=VerbCall(name="hello", version="1.0.0", args={"name": "Ada"})),
        )
        errors = static_check(program, lib, frozenset({PolicyDomain.READ}))
        self.assertEqual(errors, [])

    def test_static_check_policy_violation(self):
        lib = _verb_library()
        program = make_sequence(
            VerbCallStep(call=VerbCall(name="write_note", version="1.0.0", args={"text": "x"})),
        )
        errors = static_check(program, lib, frozenset({PolicyDomain.READ}))
        self.assertTrue(any("policy violation" in e for e in errors))

    def test_runtime_success_and_audit_chain(self):
        lib = _verb_library()
        runtime = VerbRuntime(library=lib, state={"flag": True})
        program = make_sequence(
            VerbCallStep(call=VerbCall(name="hello", version="1.0.0", args={"name": "Ada"})),
            ConditionalStep(
                guard=lambda state: True,
                if_true=VerbCallStep(call=VerbCall(name="write_note", version="1.0.0", args={"text": "hi"})),
                description="always",
            ),
        )
        exec_result = execute_program(program, runtime, program_id="p1")
        self.assertTrue(exec_result.success)
        self.assertEqual([r.name for r in exec_result.results], ["hello", "write_note"])
        self.assertEqual(len(runtime.audit), 2)
        self.assertTrue(runtime.audit.verify())

    def test_precondition_failure(self):
        lib = _verb_library()
        runtime = VerbRuntime(library=lib)
        result = runtime.invoke(VerbCall(name="hello", version="1.0.0", args={"name": "Ada"}), program_id="p2", step_index=0)
        self.assertFalse(result.success)
        self.assertTrue(result.pre_failures)

    def test_collect_calls(self):
        program = make_sequence(
            VerbCallStep(call=VerbCall(name="hello", version="1.0.0", args={"name": "Ada"})),
        )
        calls = collect_verb_calls(program)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].name, "hello")

    def test_builtin_runtime(self):
        runtime = create_typed_verb_runtime()
        self.assertTrue(len(runtime.library) >= 4)


if __name__ == "__main__":
    unittest.main()
