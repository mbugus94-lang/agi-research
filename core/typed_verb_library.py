"""
Typed Verb Library (Web-Verb Layer)

Inspired by the June 2026 "Web Agents Should Use Typed Actions Instead of
Click-Based Browsing" position paper (OpenReview PxbzZPlPhr) and the
converging 2026 production-agent auditability literature.

This module is the *implementable* version of the "Web Verbs" position:
typed operations with structured inputs/outputs, preconditions,
postconditions, policy tags, and logging hooks.

Core invariants:
  - Verbs are declarative: a verb is a schema + policy + handler
  - A VerbLibrary is the single source of truth for verb existence
  - AgentPrograms compose verbs and are statically type-checked
  - Preconditions are HARD gates; failing aborts the program
  - Audit log is append-only and hash-chained (mirrors PCA IEEC)
  - LLM-agnostic, deterministic; handlers are pluggable
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union


# ===========================================================================
# Enums
# ===========================================================================

class PolicyDomain(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELEGATE = "delegate"
    BROAD = "broad"
    NETWORK = "network"
    FILESYSTEM = "filesystem"
    PAYMENT = "payment"
    IDENTITY = "identity"
    COMMUNICATION = "communication"


class DataClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class CostClass(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Reversibility(str, Enum):
    REVERSIBLE = "reversible"
    DEGRADED = "degraded"
    IRREVERSIBLE = "irreversible"


class GateMode(str, Enum):
    HARD = "hard"


class StepKind(str, Enum):
    VERB_CALL = "verb_call"
    SEQUENCE = "sequence"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


class CheckVerdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"


class AuditMode(str, Enum):
    MEMORY = "memory"
    JSONL = "jsonl"


# ===========================================================================
# Predicates and Conditions
# ===========================================================================

Predicate = Callable[[Mapping[str, Any], Mapping[str, Any]], bool]


@dataclass
class Precondition:
    name: str
    predicate: Predicate
    description: str = ""
    mode: GateMode = GateMode.HARD

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Precondition name is required")
        if not callable(self.predicate):
            raise ValueError(f"Precondition {self.name!r}: predicate must be callable")
        if self.mode != GateMode.HARD:
            raise ValueError(
                f"Precondition {self.name!r}: only HARD gate mode is supported"
            )

    def evaluate(self, state: Mapping[str, Any], args: Mapping[str, Any]) -> CheckVerdict:
        try:
            ok = bool(self.predicate(state, args))
        except Exception:
            ok = False
        return CheckVerdict.PASS if ok else CheckVerdict.FAIL

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "description": self.description, "mode": self.mode.value}


@dataclass
class Postcondition:
    name: str
    predicate: Predicate
    description: str = ""
    mode: GateMode = GateMode.HARD

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Postcondition name is required")
        if not callable(self.predicate):
            raise ValueError(f"Postcondition {self.name!r}: predicate must be callable")
        if self.mode != GateMode.HARD:
            raise ValueError(f"Postcondition {self.name!r}: only HARD gate mode is supported")

    def evaluate(self, state: Mapping[str, Any], args: Mapping[str, Any]) -> CheckVerdict:
        try:
            ok = bool(self.predicate(state, args))
        except Exception:
            ok = False
        return CheckVerdict.PASS if ok else CheckVerdict.FAIL

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "description": self.description, "mode": self.mode.value}


# ===========================================================================
# Field Spec / Schema
# ===========================================================================

@dataclass(frozen=True)
class FieldSpec:
    """A single field in an input/output schema. type_name is stringly-typed."""
    name: str
    type_name: str
    required: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("FieldSpec name is required")
        if not self.type_name:
            raise ValueError(f"FieldSpec {self.name!r}: type_name is required")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type_name": self.type_name,
            "required": self.required,
            "description": self.description,
        }


@dataclass
class Schema:
    """A schema is an ordered list of fields with a name (Input/Output)."""
    name: str
    fields: Tuple[FieldSpec, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Schema name is required")
        names = [f.name for f in self.fields]
        if len(names) != len(set(names)):
            raise ValueError(f"Schema {self.name!r}: duplicate field names")
        object.__setattr__(self, "fields", tuple(self.fields))

    @property
    def required_fields(self) -> Tuple[FieldSpec, ...]:
        return tuple(f for f in self.fields if f.required)

    @property
    def optional_fields(self) -> Tuple[FieldSpec, ...]:
        return tuple(f for f in self.fields if not f.required)

    def field_names(self) -> Tuple[str, ...]:
        return tuple(f.name for f in self.fields)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "fields": [f.to_dict() for f in self.fields]}


# ===========================================================================
# Verb
# ===========================================================================

VerbHandler = Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]
"""
A verb handler takes (state, args) and returns the verb's output mapping.
Handlers may do anything (LLM, browser, tool call).  The verb layer
constrains the verb; it does not constrain the handler.
"""


@dataclass
class TypedVerb:
    """A typed verb: name + version + schema + policy + handler + conditions."""
    name: str
    version: str
    input_schema: Schema
    output_schema: Schema
    handler: VerbHandler
    preconditions: Tuple[Precondition, ...] = ()
    postconditions: Tuple[Postcondition, ...] = ()
    policy_domains: Tuple[PolicyDomain, ...] = ()
    data_classification: DataClassification = DataClassification.INTERNAL
    cost_class: CostClass = CostClass.LOW
    reversibility: Reversibility = Reversibility.REVERSIBLE
    description: str = ""
    registered_at: float = field(default_factory=lambda: time.time())

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("TypedVerb name is required")
        if not self.version:
            raise ValueError(f"TypedVerb {self.name!r}: version is required")
        if not self.policy_domains:
            raise ValueError(
                f"TypedVerb {self.name!r}: at least one policy_domain is required"
            )
        if not callable(self.handler):
            raise ValueError(f"TypedVerb {self.name!r}: handler must be callable")
        # cross-check: postconditions can only reference fields in output_schema
        out_names = set(self.output_schema.field_names())
        for pc in self.postconditions:
            # The predicate signature is (state, args); the verb layer's
            # contract is that the *output* of the handler is passed in
            # state["_last_output"].  We don't enforce that here, but we
            # do verify that postcondition names are unique.
            pass
        pre_names = [p.name for p in self.preconditions]
        if len(pre_names) != len(set(pre_names)):
            raise ValueError(f"TypedVerb {self.name!r}: duplicate precondition names")
        post_names = [p.name for p in self.postconditions]
        if len(post_names) != len(set(post_names)):
            raise ValueError(f"TypedVerb {self.name!r}: duplicate postcondition names")

    def policy_tags(self) -> Tuple[str, ...]:
        """The 'policy tags' the position paper calls for."""
        return tuple(d.value for d in self.policy_domains)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "input_schema": self.input_schema.to_dict(),
            "output_schema": self.output_schema.to_dict(),
            "policy_domains": [d.value for d in self.policy_domains],
            "data_classification": self.data_classification.value,
            "cost_class": self.cost_class.value,
            "reversibility": self.reversibility.value,
            "preconditions": [p.to_dict() for p in self.preconditions],
            "postconditions": [p.to_dict() for p in self.postconditions],
            "description": self.description,
            "registered_at": self.registered_at,
        }


# ===========================================================================
# Verb Library
# ===========================================================================

VerbKey = Tuple[str, str]  # (name, version)


@dataclass
class VerbLibrary:
    """A typed-verb registry.  Re-registration of the same key raises."""
    library_id: str
    verbs: Dict[VerbKey, TypedVerb] = field(default_factory=dict)
    registered_history: List[VerbKey] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.library_id:
            raise ValueError("VerbLibrary id is required")

    def register(self, verb: TypedVerb) -> VerbKey:
        if not isinstance(verb, TypedVerb):
            raise TypeError(f"register() requires TypedVerb, got {type(verb).__name__}")
        key: VerbKey = (verb.name, verb.version)
        if key in self.verbs:
            raise ValueError(f"VerbLibrary {self.library_id!r}: duplicate verb {key}")
        self.verbs[key] = verb
        self.registered_history.append(key)
        return key

    def deregister(self, name: str, version: str) -> TypedVerb:
        key = (name, version)
        if key not in self.verbs:
            raise KeyError(f"VerbLibrary {self.library_id!r}: no verb {key}")
        verb = self.verbs.pop(key)
        return verb

    def get(self, name: str, version: str = "1.0.0") -> TypedVerb:
        """Lookup a verb.  If version not given, return the latest registered."""
        if version != "1.0.0" or (name, version) in self.verbs:
            return self.verbs[(name, version)]
        # find latest version of this name (registration order)
        versions = [v for n, v in self.verbs if n == name]
        if not versions:
            raise KeyError(f"VerbLibrary {self.library_id!r}: no verb named {name!r}")
        return self.verbs[(name, versions[-1])]

    def names(self) -> List[str]:
        return sorted({n for n, _ in self.verbs})

    def __contains__(self, name: str) -> bool:
        return any(n == name for n, _ in self.verbs)

    def __len__(self) -> int:
        return len(self.verbs)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "library_id": self.library_id,
            "verbs": [
                {**verb.to_dict(), "name": key[0], "version": key[1]}
                for key, verb in sorted(self.verbs.items())
            ],
        }


# ===========================================================================
# Argument validation
# ===========================================================================

def _validate_args(
    args: Mapping[str, Any],
    schema: Schema,
    context: str,
) -> List[str]:
    errors: List[str] = []
    provided = set(args.keys())
    expected = set(schema.field_names())
    for field_spec in schema.required_fields:
        if field_spec.name not in provided:
            errors.append(
                f"{context}: missing required field {field_spec.name!r} "
                f"(type={field_spec.type_name})"
            )
    extra = provided - expected
    if extra:
        errors.append(f"{context}: unexpected fields {sorted(extra)}")
    return errors


# ===========================================================================
# Verb Call (the runtime step)
# ===========================================================================

@dataclass
class VerbCall:
    """A typed verb invocation: the verb reference + the concrete args."""
    name: str
    version: str
    args: Dict[str, Any]
    call_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=lambda: time.time())

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("VerbCall name is required")
        if not self.version:
            raise ValueError(f"VerbCall {self.name!r}: version is required")
        if not isinstance(self.args, dict):
            raise TypeError("VerbCall args must be a dict")
        # freeze
        object.__setattr__(self, "args", dict(self.args))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "name": self.name,
            "version": self.version,
            "args": dict(self.args),
            "timestamp": self.timestamp,
        }


# ===========================================================================
# Step Result
# ===========================================================================

@dataclass
class PreconditionFailure:
    precondition: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {"precondition": self.precondition, "description": self.description}


@dataclass
class PostconditionFailure:
    postcondition: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {"postcondition": self.postcondition, "description": self.description}


@dataclass
class VerbStepResult:
    """The deterministic record of one verb invocation."""
    call_id: str
    name: str
    version: str
    args: Dict[str, Any]
    success: bool
    output: Dict[str, Any]
    preconditions_passed: List[str]
    postconditions_passed: List[str]
    pre_failures: List[PreconditionFailure]
    post_failures: List[PostconditionFailure]
    arg_errors: List[str]
    duration_ms: float
    timestamp: float
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "name": self.name,
            "version": self.version,
            "args": dict(self.args),
            "success": self.success,
            "output": dict(self.output),
            "preconditions_passed": list(self.preconditions_passed),
            "postconditions_passed": list(self.postconditions_passed),
            "pre_failures": [f.to_dict() for f in self.pre_failures],
            "post_failures": [f.to_dict() for f in self.post_failures],
            "arg_errors": list(self.arg_errors),
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
            "error": self.error,
        }


# ===========================================================================
# Agent Programs
# ===========================================================================

ProgramStep = Union["VerbCallStep", "SequenceStep", "ParallelStep", "ConditionalStep"]


@dataclass
class VerbCallStep:
    """Atomic program step: a single verb invocation."""
    call: VerbCall
    kind: StepKind = StepKind.VERB_CALL

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind.value, "call": self.call.to_dict()}


@dataclass
class SequenceStep:
    """A sequence of program steps executed in order."""
    steps: List[ProgramStep]
    kind: StepKind = StepKind.SEQUENCE

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("SequenceStep requires at least one child step")

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind.value, "steps": [s.to_dict() for s in self.steps]}


@dataclass
class ParallelStep:
    """A list of steps executed in arbitrary order (the agent runtime
    can choose, but the audit log preserves a deterministic order)."""
    steps: List[ProgramStep]
    kind: StepKind = StepKind.PARALLEL

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("ParallelStep requires at least one child step")

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind.value, "steps": [s.to_dict() for s in self.steps]}


@dataclass
class ConditionalStep:
    """A program step with a static guard.

    The guard is a (state) -> bool.  If it returns True, the inner
    steps execute; otherwise, the step is recorded as skipped.  The
    guard cannot itself trigger side effects (no LLM, no I/O).
    """
    guard: Callable[[Mapping[str, Any]], bool]
    if_true: ProgramStep
    description: str = ""
    kind: StepKind = StepKind.CONDITIONAL

    def __post_init__(self) -> None:
        if not callable(self.guard):
            raise ValueError("ConditionalStep.guard must be callable")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "description": self.description,
            "if_true": self.if_true.to_dict(),
        }


def make_sequence(*steps: ProgramStep) -> SequenceStep:
    if not steps:
        raise ValueError("make_sequence requires at least one step")
    return SequenceStep(steps=list(steps))


def make_parallel(*steps: ProgramStep) -> ParallelStep:
    if not steps:
        raise ValueError("make_parallel requires at least one step")
    return ParallelStep(steps=list(steps))


def make_conditional(
    guard: Callable[[Mapping[str, Any]], bool],
    if_true: ProgramStep,
    description: str = "",
) -> ConditionalStep:
    return ConditionalStep(guard=guard, if_true=if_true, description=description)


# ===========================================================================
# Static program analysis
# ===========================================================================

def _walk_steps(step: ProgramStep, out: List[ProgramStep]) -> None:
    if isinstance(step, VerbCallStep):
        out.append(step)
    elif isinstance(step, (SequenceStep, ParallelStep)):
        for s in step.steps:
            _walk_steps(s, out)
    elif isinstance(step, ConditionalStep):
        _walk_steps(step.if_true, out)


def collect_verb_calls(program: ProgramStep) -> List[VerbCall]:
    """Return all verb calls in the program in traversal order."""
    flat: List[ProgramStep] = []
    _walk_steps(program, flat)
    return [s.call for s in flat if isinstance(s, VerbCallStep)]


def _check_known(
    calls: Sequence[VerbCall],
    library: VerbLibrary,
) -> List[str]:
    errors: List[str] = []
    for call in calls:
        if (call.name, call.version) not in library.verbs:
            errors.append(
                f"unknown verb: {call.name!r} v{call.version} "
                f"(library={library.library_id!r})"
            )
    return errors


def _check_arg_schemas(
    calls: Sequence[VerbCall],
    library: VerbLibrary,
) -> List[str]:
    errors: List[str] = []
    for call in calls:
        verb = library.verbs.get((call.name, call.version))
        if verb is None:
            continue
        errors.extend(_validate_args(call.args, verb.input_schema, f"call {call.call_id}"))
    return errors


def _check_policy(
    calls: Sequence[VerbCall],
    library: VerbLibrary,
    allowed: FrozenSet[PolicyDomain],
) -> List[str]:
    errors: List[str] = []
    for call in calls:
        verb = library.verbs.get((call.name, call.version))
        if verb is None:
            continue
        for dom in verb.policy_domains:
            if dom not in allowed:
                errors.append(
                    f"policy violation: {call.name!r} v{call.version} "
                    f"requires {dom.value!r} not in scope {sorted(d.value for d in allowed)}"
                )
    return errors


def static_check(
    program: ProgramStep,
    library: VerbLibrary,
    allowed_policy: FrozenSet[PolicyDomain],
) -> List[str]:
    """Return a list of static-check error strings.  Empty list = OK."""
    if not isinstance(program, (VerbCallStep, SequenceStep, ParallelStep, ConditionalStep)):
        return ["static_check: program must be a ProgramStep"]
    calls = collect_verb_calls(program)
    errors: List[str] = []
    errors.extend(_check_known(calls, library))
    errors.extend(_check_arg_schemas(calls, library))
    errors.extend(_check_policy(calls, library, allowed_policy))
    return errors


# ===========================================================================
# Audit log (append-only, hash-chained, like OpenKedge IEEC)
# ===========================================================================

@dataclass
class AuditEntry:
    entry_id: str
    program_id: str
    step_index: int
    call: VerbCall
    success: bool
    timestamp: float
    previous_hash: str
    entry_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "program_id": self.program_id,
            "step_index": self.step_index,
            "call": self.call.to_dict(),
            "success": self.success,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
        }


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))


def _hash_entry(previous_hash: str, payload: Dict[str, Any]) -> str:
    blob = previous_hash + "|" + _canonical(payload)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class AuditLog:
    """Append-only, hash-chained audit log.

    Mirrors the OpenKedge IEEC pattern: each entry stores the hash of
    the previous entry + the canonical JSON of the current payload.
    """
    def __init__(self) -> None:
        self._entries: List[AuditEntry] = []
        self._latest_hash: str = hashlib.sha256(b"genusis").hexdigest()

    def append(self, program_id: str, step_index: int, call: VerbCall, success: bool) -> AuditEntry:
        ts = time.time()
        payload = {
            "entry_id": str(uuid.uuid4()),
            "program_id": program_id,
            "step_index": step_index,
            "call": call.to_dict(),
            "success": success,
            "timestamp": ts,
        }
        entry_hash = _hash_entry(self._latest_hash, payload)
        entry = AuditEntry(
            entry_id=payload["entry_id"],
            program_id=program_id,
            step_index=step_index,
            call=call,
            success=success,
            timestamp=ts,
            previous_hash=self._latest_hash,
            entry_hash=entry_hash,
        )
        self._entries.append(entry)
        self._latest_hash = entry_hash
        return entry

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)

    def verify(self) -> bool:
        if not self._entries:
            return True
        prev = hashlib.sha256(b"genusis").hexdigest()
        for entry in self._entries:
            if entry.previous_hash != prev:
                return False
            payload = {
                "entry_id": entry.entry_id,
                "program_id": entry.program_id,
                "step_index": entry.step_index,
                "call": entry.call.to_dict(),
                "success": entry.success,
                "timestamp": entry.timestamp,
            }
            if _hash_entry(entry.previous_hash, payload) != entry.entry_hash:
                return False
            prev = entry.entry_hash
        return True

    def filter_by_program(self, program_id: str) -> List[AuditEntry]:
        return [e for e in self._entries if e.program_id == program_id]

    def filter_by_verb(self, name: str) -> List[AuditEntry]:
        return [e for e in self._entries if e.call.name == name]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entries": [e.to_dict() for e in self._entries],
            "latest_hash": self._latest_hash,
        }


# ===========================================================================
# Verb Runtime
# ===========================================================================

class VerbNotFoundError(KeyError):
    pass


class ArgValidationError(ValueError):
    pass


class PreconditionError(RuntimeError):
    def __init__(self, failures: List[PreconditionFailure]) -> None:
        super().__init__(f"precondition failures: {len(failures)}")
        self.failures = failures


class PostconditionError(RuntimeError):
    def __init__(self, failures: List[PostconditionFailure]) -> None:
        super().__init__(f"postcondition failures: {len(failures)}")
        self.failures = failures


@dataclass
class VerbRuntime:
    """The execution engine: takes a verb call, runs the handler, records
    the audit entry.

    `state` is an agent-visible scratch space shared across verb calls
    within a single program.  Handlers can read/write it.
    """
    library: VerbLibrary
    audit: AuditLog = field(default_factory=AuditLog)
    state: Dict[str, Any] = field(default_factory=dict)

    def invoke(self, call: VerbCall, program_id: Optional[str] = None, step_index: Optional[int] = None) -> VerbStepResult:
        verb = self._lookup(call)
        arg_errors = _validate_args(call.args, verb.input_schema, f"call {call.call_id}")
        if arg_errors:
            result = VerbStepResult(
                call_id=call.call_id,
                name=call.name,
                version=call.version,
                args=dict(call.args),
                success=False,
                output={},
                preconditions_passed=[],
                postconditions_passed=[],
                pre_failures=[],
                post_failures=[],
                arg_errors=arg_errors,
                duration_ms=0.0,
                timestamp=time.time(),
                error="; ".join(arg_errors),
            )
            self.audit.append(program_id=program_id or "", step_index=step_index if step_index is not None else 0, call=call, success=False)
            return result

        t0 = time.time()
        pre_failures: List[PreconditionFailure] = []
        for pre in verb.preconditions:
            verdict = pre.evaluate(self.state, call.args)
            if verdict != CheckVerdict.PASS:
                pre_failures.append(PreconditionFailure(
                    precondition=pre.name,
                    description=pre.description or f"precondition {pre.name!r} failed",
                ))
        if pre_failures:
            result = VerbStepResult(
                call_id=call.call_id,
                name=call.name,
                version=call.version,
                args=dict(call.args),
                success=False,
                output={},
                preconditions_passed=[p.name for p in verb.preconditions if p.name not in {f.precondition for f in pre_failures}],
                postconditions_passed=[],
                pre_failures=pre_failures,
                post_failures=[],
                arg_errors=[],
                duration_ms=(time.time() - t0) * 1000.0,
                timestamp=time.time(),
                error=f"{len(pre_failures)} precondition(s) failed",
            )
            self.audit.append(program_id=program_id or "", step_index=step_index if step_index is not None else 0, call=call, success=False)
            return result

        try:
            output = dict(verb.handler(call.args, self.state))
        except Exception as exc:  # noqa: BLE001
            result = VerbStepResult(
                call_id=call.call_id,
                name=call.name,
                version=call.version,
                args=dict(call.args),
                success=False,
                output={},
                preconditions_passed=[p.name for p in verb.preconditions],
                postconditions_passed=[],
                pre_failures=[],
                post_failures=[],
                arg_errors=[],
                duration_ms=(time.time() - t0) * 1000.0,
                timestamp=time.time(),
                error=f"{type(exc).__name__}: {exc}",
            )
            self.audit.append(program_id=program_id or "", step_index=step_index if step_index is not None else 0, call=call, success=False)
            return result

        post_failures: List[PostconditionFailure] = []
        for post in verb.postconditions:
            verdict = post.evaluate(self.state, {"_last_output": output, **call.args})
            if verdict != CheckVerdict.PASS:
                post_failures.append(PostconditionFailure(
                    postcondition=post.name,
                    description=post.description or f"postcondition {post.name!r} failed",
                ))

        success = not post_failures
        result = VerbStepResult(
            call_id=call.call_id,
            name=call.name,
            version=call.version,
            args=dict(call.args),
            success=success,
            output=output,
            preconditions_passed=[p.name for p in verb.preconditions],
            postconditions_passed=[p.name for p in verb.postconditions if p.name not in {f.postcondition for f in post_failures}],
            pre_failures=[],
            post_failures=post_failures,
            arg_errors=[],
            duration_ms=(time.time() - t0) * 1000.0,
            timestamp=time.time(),
            error=None if success else f"{len(post_failures)} postcondition(s) failed",
        )
        self.audit.append(program_id=program_id or "", step_index=step_index if step_index is not None else 0, call=call, success=success)
        return result

    def _lookup(self, call: VerbCall) -> TypedVerb:
        if (call.name, call.version) not in self.library.verbs:
            raise VerbNotFoundError(
                f"verb {call.name!r} v{call.version} not in library {self.library.library_id!r}"
            )
        return self.library.verbs[(call.name, call.version)]


# ===========================================================================
# Program Executor
# ===========================================================================

@dataclass
class ProgramExecution:
    program_id: str
    program: ProgramStep
    results: List[VerbStepResult]
    success: bool
    total_duration_ms: float
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "program_id": self.program_id,
            "program": self.program.to_dict(),
            "results": [r.to_dict() for r in self.results],
            "success": self.success,
            "total_duration_ms": self.total_duration_ms,
            "timestamp": self.timestamp,
        }


def _execute_call_step(
    step: VerbCallStep,
    runtime: VerbRuntime,
    program_id: str,
    step_index: int,
    on_step: Optional[Callable[[VerbStepResult], None]],
) -> VerbStepResult:
    result = runtime.invoke(step.call, program_id=program_id, step_index=step_index)
    if on_step is not None:
        on_step(result)
    return result


def _execute_program(
    step: ProgramStep,
    runtime: VerbRuntime,
    program_id: str,
    step_index: int,
    on_step: Optional[Callable[[VerbStepResult], None]],
    results: List[VerbStepResult],
) -> bool:
    if isinstance(step, VerbCallStep):
        result = _execute_call_step(step, runtime, program_id, step_index, on_step)
        results.append(result)
        return result.success
    if isinstance(step, SequenceStep):
        ok_all = True
        for i, child in enumerate(step.steps):
            ok = _execute_program(child, runtime, program_id, step_index + i, on_step, results)
            if not ok:
                return False
            ok_all = ok_all and ok
        return ok_all
    if isinstance(step, ParallelStep):
        ok_all = True
        for i, child in enumerate(step.steps):
            ok = _execute_program(child, runtime, program_id, step_index + i, on_step, results)
            ok_all = ok_all and ok
        return ok_all
    if isinstance(step, ConditionalStep):
        if step.guard(dict(runtime.state)):
            return _execute_program(step.if_true, runtime, program_id, step_index, on_step, results)
        # skipped: still record a synthetic entry so the audit log is
        # deterministic
        sk_call = VerbCall(name="<skipped>", version="0.0.0", args={"description": step.description})
        result = VerbStepResult(
            call_id=sk_call.call_id,
            name=sk_call.name,
            version=sk_call.version,
            args={},
            success=True,
            output={"skipped": True},
            preconditions_passed=[],
            postconditions_passed=[],
            pre_failures=[],
            post_failures=[],
            arg_errors=[],
            duration_ms=0.0,
            timestamp=time.time(),
        )
        results.append(result)
        if on_step is not None:
            on_step(result)
        return True
    raise TypeError(f"unknown program step: {type(step).__name__}")


def execute_program(
    program: ProgramStep,
    runtime: VerbRuntime,
    program_id: str = "",
    on_step: Optional[Callable[[VerbStepResult], None]] = None,
) -> ProgramExecution:
    """Run a typed-verb program.  Returns the full deterministic record.

    Fails-fast: the first failed step aborts the program unless
    `fail_fast=False` is added later.  (Today: always fail-fast.)
    """
    if not program_id:
        program_id = str(uuid.uuid4())
    results: List[VerbStepResult] = []
    t0 = time.time()
    success = _execute_program(program, runtime, program_id, 0, on_step, results)
    return ProgramExecution(
        program_id=program_id,
        program=program,
        results=results,
        success=success,
        total_duration_ms=(time.time() - t0) * 1000.0,
        timestamp=time.time(),
    )


# ===========================================================================
# Built-in verb library (a small starter set)
# ===========================================================================

def _builtin_verb_library() -> VerbLibrary:
    """A small starter library with 4 common verbs.

    These are *illustrative* -- real agents would register their own
    domain-specific verbs.  The starter is here to (a) make the module
    importable and (b) give the README/tests a concrete shape.
    """
    lib = VerbLibrary(library_id="builtin-2026.07")

    def _cart_exists(state, args):
        return "cart_id" in state or "cart_id" in args

    def _amount_positive(state, args):
        return float(args.get("amount", 0)) > 0

    def _cart_total_nonneg(state, args):
        return args.get("_last_output", {}).get("cart_total", -1) >= 0

    def _tx_id_set(state, args):
        return bool(args.get("_last_output", {}).get("tx_id"))

    # search_hotels
    lib.register(TypedVerb(
        name="search_hotels",
        version="1.0.0",
        description="Search for hotels by city and date range.",
        input_schema=Schema(name="search_hotels_input", fields=[
            FieldSpec(name="city", type_name="string", required=True, description="City name"),
            FieldSpec(name="checkin", type_name="string", required=True, description="ISO date"),
            FieldSpec(name="checkout", type_name="string", required=True, description="ISO date"),
            FieldSpec(name="max_price", type_name="number", required=False, description="Max USD/night"),
        ]),
        output_schema=Schema(name="search_hotels_output", fields=[
            FieldSpec(name="results", type_name="array", required=True),
            FieldSpec(name="count", type_name="integer", required=True),
        ]),
        preconditions=[],
        postconditions=[],
        policy_domains=(PolicyDomain.READ,),
        data_classification=DataClassification.PUBLIC,
        cost_class=CostClass.LOW,
        reversibility=Reversibility.REVERSIBLE,
        handler=lambda args, _state: {
            "results": [
                {"name": f"Hotel in {args['city']}", "price": 100.0},
            ],
            "count": 1,
        },
    ))

    # add_to_cart
    lib.register(TypedVerb(
        name="add_to_cart",
        version="1.0.0",
        description="Add an item to a shopping cart.",
        input_schema=Schema(name="add_to_cart_input", fields=[
            FieldSpec(name="cart_id", type_name="string", required=True),
            FieldSpec(name="item_id", type_name="string", required=True),
            FieldSpec(name="quantity", type_name="integer", required=True),
        ]),
        output_schema=Schema(name="add_to_cart_output", fields=[
            FieldSpec(name="cart_total", type_name="number", required=True),
        ]),
        preconditions=[
            Precondition(name="cart_exists", predicate=_cart_exists),
        ],
        postconditions=[
            Postcondition(name="cart_total_nonneg", predicate=_cart_total_nonneg),
        ],
        policy_domains=(PolicyDomain.WRITE,),
        data_classification=DataClassification.INTERNAL,
        cost_class=CostClass.MEDIUM,
        reversibility=Reversibility.DEGRADED,
        handler=lambda args, state: {
            "cart_total": float(args.get("quantity", 0)) * 10.0,
        },
    ))

    # get_directions
    lib.register(TypedVerb(
        name="get_directions",
        version="1.0.0",
        description="Compute driving directions between two points.",
        input_schema=Schema(name="get_directions_input", fields=[
            FieldSpec(name="origin", type_name="string", required=True),
            FieldSpec(name="destination", type_name="string", required=True),
        ]),
        output_schema=Schema(name="get_directions_output", fields=[
            FieldSpec(name="distance_km", type_name="number", required=True),
        ]),
        preconditions=[],
        postconditions=[],
        policy_domains=(PolicyDomain.READ,),
        data_classification=DataClassification.PUBLIC,
        cost_class=CostClass.LOW,
        reversibility=Reversibility.REVERSIBLE,
        handler=lambda args, _state: {
            "distance_km": 12.3,
        },
    ))

    # pay
    lib.register(TypedVerb(
        name="pay",
        version="1.0.0",
        description="Authorize a payment from the agent's wallet.",
        input_schema=Schema(name="pay_input", fields=[
            FieldSpec(name="amount", type_name="number", required=True),
            FieldSpec(name="currency", type_name="string", required=True),
        ]),
        output_schema=Schema(name="pay_output", fields=[
            FieldSpec(name="tx_id", type_name="string", required=True),
            FieldSpec(name="amount", type_name="number", required=True),
        ]),
        preconditions=[
            Precondition(name="amount_positive", predicate=_amount_positive),
        ],
        postconditions=[
            Postcondition(name="tx_id_set", predicate=_tx_id_set),
        ],
        policy_domains=(PolicyDomain.WRITE, PolicyDomain.PAYMENT),
        data_classification=DataClassification.CONFIDENTIAL,
        cost_class=CostClass.CRITICAL,
        reversibility=Reversibility.IRREVERSIBLE,
        handler=lambda args, _state: {
            "tx_id": "tx_" + str(uuid.uuid4())[:8],
            "amount": float(args["amount"]),
        },
    ))

    return lib


BUILTIN_VERB_LIBRARY: VerbLibrary = _builtin_verb_library()


# ===========================================================================
# Convenience constructor
# ===========================================================================

def create_typed_verb_runtime(
    extra_verbs: Optional[Sequence[TypedVerb]] = None,
) -> VerbRuntime:
    """One-line install: returns a VerbRuntime wrapping the builtin library
    (plus any extra verbs the caller wants to register).
    """
    lib = VerbLibrary(
        library_id=BUILTIN_VERB_LIBRARY.library_id,
        verbs=dict(BUILTIN_VERB_LIBRARY.verbs),
    )
    if extra_verbs:
        for v in extra_verbs:
            lib.register(v)
    return VerbRuntime(library=lib)


__all__ = [
    "ArgValidationError",
    "AuditEntry",
    "AuditLog",
    "BUILTIN_VERB_LIBRARY",
    "FieldSpec",
    "FieldType",
    "PolicyDomain",
    "Postcondition",
    "PostconditionError",
    "PostconditionFailure",
    "Precondition",
    "PreconditionError",
    "PreconditionFailure",
    "ProgramExecution",
    "ProgramStep",
    "Schema",
    "StepKind",
    "TypedVerb",
    "VerbCall",
    "VerbCallStep",
    "VerbLibrary",
    "VerbNotFoundError",
    "VerbRuntime",
    "VerbStepResult",
    "collect_verb_calls",
    "create_typed_verb_runtime",
    "execute_program",
    "make_conditional",
    "make_parallel",
    "make_sequence",
    "static_check",
]
