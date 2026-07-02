"""Typed Verb CEF Guard bridge (part 1/3)."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple

try:
    from .cef_detector import (
        CEFAction as _CEFAction,
        CEFDetection as _CEFDetection,
        CEFDetector as _CEFDetector,
        CEFSeverity as _CEFSeverity,
        CEFType as _CEFType,
        create_cef_detector as _create_cef_detector,
    )
    _CEF_AVAILABLE = True
except Exception:
    _CEFAction = None
    _CEFDetection = None
    _CEFDetector = None
    _CEFSeverity = None
    _CEFType = None
    _create_cef_detector = None
    _CEF_AVAILABLE = False


class VerbGuardAction(str, Enum):
    NONE = "none"
    LOG = "log"
    FLAG = "flag"
    HALT = "halt"
    ESCALATE = "escalate"


class CEFGuardAvailability(str, Enum):
    AVAILABLE = "available"
    NO_CEF_SUBSTRATE = "no_cef_substrate"
    DISABLED = "disabled"


@dataclass(frozen=True)
class VerbOutputCEFInspection:
    call_id: str
    verb_name: str
    verb_version: str
    program_id: str
    step_index: int
    scanned_fields: Tuple[str, ...]
    aggregate_text_hash: str
    aggregate_text_length: int
    detection: Optional[Any]
    guard_action: VerbGuardAction
    is_clean: bool
    inspected_at: float
    availability: CEFGuardAvailability

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "verb_name": self.verb_name,
            "verb_version": self.verb_version,
            "program_id": self.program_id,
            "step_index": self.step_index,
            "scanned_fields": list(self.scanned_fields),
            "aggregate_text_hash": self.aggregate_text_hash,
            "aggregate_text_length": self.aggregate_text_length,
            "detection": self.detection.to_dict() if self.detection is not None else None,
            "guard_action": self.guard_action.value,
            "is_clean": self.is_clean,
            "inspected_at": self.inspected_at,
            "availability": self.availability.value,
        }

@dataclass
class VerbCEFGuardConfig:
    low_action: VerbGuardAction = VerbGuardAction.LOG
    medium_action: VerbGuardAction = VerbGuardAction.FLAG
    high_action: VerbGuardAction = VerbGuardAction.HALT
    critical_action: VerbGuardAction = VerbGuardAction.ESCALATE
    none_action: VerbGuardAction = VerbGuardAction.NONE
    min_output_length: int = 12
    max_fields_to_scan: int = 32
    max_string_length_per_field: int = 8192

    def map_severity(self, severity):
        if not _CEF_AVAILABLE or severity is None:
            return self.none_action
        if severity == _CEFSeverity.NONE:
            return VerbGuardAction.NONE
        if severity == _CEFSeverity.LOW:
            return self.low_action
        if severity == _CEFSeverity.MEDIUM:
            return self.medium_action
        if severity == _CEFSeverity.HIGH:
            return self.high_action
        if severity == _CEFSeverity.CRITICAL:
            return self.critical_action
        return self.none_action

    def to_dict(self):
        return {
            "low_action": self.low_action.value,
            "medium_action": self.medium_action.value,
            "high_action": self.high_action.value,
            "critical_action": self.critical_action.value,
            "none_action": self.none_action.value,
            "min_output_length": self.min_output_length,
            "max_fields_to_scan": self.max_fields_to_scan,
            "max_string_length_per_field": self.max_string_length_per_field,
        }


def _collect_strings(output, max_fields, max_string_length):
    pairs = []
    for key in sorted(output.keys(), key=str)[:max_fields]:
        value = output[key]
        if isinstance(value, str):
            if len(value) > max_string_length:
                value = value[:max_string_length]
            pairs.append((str(key), value))
        elif isinstance(value, (dict, list)):
            try:
                rendered = json.dumps(value, sort_keys=True, default=str)
            except Exception:
                rendered = str(value)
            if len(rendered) > max_string_length:
                rendered = rendered[:max_string_length]
            pairs.append((str(key), rendered))
    return tuple(pairs)


def _aggregate_text_hash(pairs):
    blob = "|".join(f"{k}={v}" for k, v in pairs)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class VerbCEFGuard:
    detector: Any
    config: VerbCEFGuardConfig = field(default_factory=VerbCEFGuardConfig)
    enabled: bool = True
    availability: CEFGuardAvailability = CEFGuardAvailability.AVAILABLE

    def __post_init__(self):
        if not _CEF_AVAILABLE and self.availability == CEFGuardAvailability.AVAILABLE:
            self.availability = CEFGuardAvailability.NO_CEF_SUBSTRATE
        if self.detector is None and _create_cef_detector is not None:
            self.detector = _create_cef_detector()

    def _map_action(self, severity):
        return self.config.map_severity(severity)

    def inspect_output(
        self,
        output,
        call_id,
        verb_name,
        verb_version,
        program_id="",
        step_index=0,
    ):
        scanned = _collect_strings(
            output,
            self.config.max_fields_to_scan,
            self.config.max_string_length_per_field,
        )
        agg_hash = _aggregate_text_hash(scanned)
        agg_len = sum(len(v) for _, v in scanned)
        if not self.enabled or self.availability != CEFGuardAvailability.AVAILABLE:
            return VerbOutputCEFInspection(
                call_id=call_id,
                verb_name=verb_name,
                verb_version=verb_version,
                program_id=program_id,
                step_index=step_index,
                scanned_fields=tuple(k for k, _ in scanned),
                aggregate_text_hash=agg_hash,
                aggregate_text_length=agg_len,
                detection=None,
                guard_action=self.config.none_action,
                is_clean=True,
                inspected_at=time.time(),
                availability=self.availability,
            )
        if agg_len < self.config.min_output_length:
            return VerbOutputCEFInspection(
                call_id=call_id,
                verb_name=verb_name,
                verb_version=verb_version,
                program_id=program_id,
                step_index=step_index,
                scanned_fields=tuple(k for k, _ in scanned),
                aggregate_text_hash=agg_hash,
                aggregate_text_length=agg_len,
                detection=None,
                guard_action=VerbGuardAction.NONE,
                is_clean=True,
                inspected_at=time.time(),
                availability=self.availability,
            )
        combined = "\n".join(v for _, v in scanned)
        detection = self.detector.detect(combined)
        is_clean = detection.is_clean()
        action = self._map_action(detection.severity)
        return VerbOutputCEFInspection(
            call_id=call_id,
            verb_name=verb_name,
            verb_version=verb_version,
            program_id=program_id,
            step_index=step_index,
            scanned_fields=tuple(k for k, _ in scanned),
            aggregate_text_hash=agg_hash,
            aggregate_text_length=agg_len,
            detection=detection,
            guard_action=action,
            is_clean=is_clean,
            inspected_at=time.time(),
            availability=self.availability,
        )

@dataclass
class GuardedVerbStepResult:
    result: Any
    inspection: Any

    @property
    def success(self):
        return self.result.success

    @property
    def halted(self):
        return self.result.success is False and self.inspection.guard_action in (
            VerbGuardAction.HALT, VerbGuardAction.ESCALATE
        )

    @property
    def guard_action(self):
        return self.inspection.guard_action

    def to_dict(self):
        return {
            "result": self.result.to_dict() if self.result is not None else None,
            "inspection": self.inspection.to_dict(),
            "halted": self.halted,
        }


@dataclass
class GuardedVerbRuntime:
    runtime: Any
    guard: VerbCEFGuard
    halt_on_halt: bool = True
    inspections: List[Any] = field(default_factory=list)

    def invoke(self, call, program_id="", step_index=0):
        result = self.runtime.invoke(call, program_id=program_id, step_index=step_index)
        output = result.output if hasattr(result, "output") else {}
        inspection = self.guard.inspect_output(
            output,
            call_id=getattr(call, "call_id", ""),
            verb_name=call.name,
            verb_version=call.version,
            program_id=program_id,
            step_index=step_index,
        )
        self.inspections.append(inspection)
        if self.halt_on_halt and inspection.guard_action in (VerbGuardAction.HALT, VerbGuardAction.ESCALATE):
            from .typed_verb_library import VerbStepResult as _VSR
            halted_result = _VSR(
                call_id=result.call_id,
                name=result.name,
                version=result.version,
                args=dict(result.args),
                success=False,
                output=dict(result.output),
                preconditions_passed=list(result.preconditions_passed),
                postconditions_passed=list(result.postconditions_passed),
                pre_failures=list(result.pre_failures),
                post_failures=list(result.post_failures),
                arg_errors=list(result.arg_errors),
                duration_ms=result.duration_ms,
                timestamp=result.timestamp,
                error="CEF guard {}: {}".format(inspection.guard_action.value, getattr(inspection.detection, "rationale", "")) if inspection.detection is not None else "CEF guard {}".format(inspection.guard_action.value),
            )
            return GuardedVerbStepResult(result=halted_result, inspection=inspection)
        return GuardedVerbStepResult(result=result, inspection=inspection)

    def state(self):
        return self.runtime.state

    def audit(self):
        return self.runtime.audit


def create_verb_cef_guard(detector=None, config=None):
    return VerbCEFGuard(detector=detector, config=config or VerbCEFGuardConfig())


def create_guarded_verb_runtime(runtime, detector=None, config=None, halt_on_halt=True):
    guard = create_verb_cef_guard(detector=detector, config=config)
    return GuardedVerbRuntime(runtime=runtime, guard=guard, halt_on_halt=halt_on_halt)


def record_cef_to_evidence_ledger(inspection, ledger):
    if inspection is None or inspection.detection is None:
        return None
    if not hasattr(ledger, "record"):
        return None
    payload = inspection.detection.to_dict()
    payload["source"] = "typed_verb_cef_guard"
    payload["call_id"] = inspection.call_id
    payload["verb_name"] = inspection.verb_name
    payload["verb_version"] = inspection.verb_version
    payload["program_id"] = inspection.program_id
    payload["step_index"] = inspection.step_index
    return ledger.record(payload)


__all__ = [
    "CEFGuardAvailability",
    "GuardedVerbRuntime",
    "GuardedVerbStepResult",
    "VerbCEFGuard",
    "VerbCEFGuardConfig",
    "VerbGuardAction",
    "VerbOutputCEFInspection",
    "create_guarded_verb_runtime",
    "create_verb_cef_guard",
    "record_cef_to_evidence_ledger",
]
