"""Selective memory intervention for long-horizon agent loops."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Optional, Sequence


class MemoryKind(str, Enum):
    STATUS = "status"
    KNOWLEDGE = "knowledge"
    PROCEDURAL = "procedural"


class MemoryTrigger(str, Enum):
    REQUIREMENT = "requirement"
    ERROR = "error"
    REPEAT = "repeat"
    SUBGOAL = "subgoal"
    CONTEXT_SHIFT = "context_shift"


@dataclass
class MemoryRecord:
    memory_id: str
    content: str
    kind: MemoryKind = MemoryKind.KNOWLEDGE
    tags: tuple[str, ...] = ()
    importance: float = 0.5
    created_step: int = 0
    last_recalled_step: Optional[int] = None
    recall_count: int = 0
    stale: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["kind"] = self.kind.value
        result["tags"] = list(self.tags)
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MemoryRecord":
        return cls(
            memory_id=str(data["memory_id"]),
            content=str(data["content"]),
            kind=MemoryKind(data.get("kind", MemoryKind.KNOWLEDGE.value)),
            tags=tuple(str(tag) for tag in data.get("tags", [])),
            importance=float(data.get("importance", 0.5)),
            created_step=int(data.get("created_step", 0)),
            last_recalled_step=(
                int(data["last_recalled_step"])
                if data.get("last_recalled_step") is not None
                else None
            ),
            recall_count=int(data.get("recall_count", 0)),
            stale=bool(data.get("stale", False)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class Intervention:
    memory_id: str
    content: str
    reason: str
    score: float
    step: int
    trigger: Optional[MemoryTrigger] = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["trigger"] = self.trigger.value if self.trigger else None
        return result


@dataclass(frozen=True)
class ProactiveMemoryConfig:
    min_score: float = 0.45
    cooldown_steps: int = 2
    max_records: int = 256
    max_interventions: int = 1
    lexical_weight: float = 0.55
    importance_weight: float = 0.25
    trigger_weight: float = 0.20

    def __post_init__(self) -> None:
        if not 0 <= self.min_score <= 1:
            raise ValueError("min_score must be between 0 and 1")
        if self.cooldown_steps < 0:
            raise ValueError("cooldown_steps must be non-negative")
        if self.max_records < 1 or self.max_interventions < 1:
            raise ValueError("memory capacities must be positive")
        weights = self.lexical_weight + self.importance_weight + self.trigger_weight
        if weights <= 0:
            raise ValueError("at least one scoring weight must be positive")


class ProactiveMemoryAgent:
    """Maintain structured memory and selectively inject one reminder per step."""

    def __init__(self, config: Optional[ProactiveMemoryConfig] = None) -> None:
        self.config = config or ProactiveMemoryConfig()
        self._records: dict[str, MemoryRecord] = {}
        self._interventions: list[Intervention] = []

    @property
    def records(self) -> tuple[MemoryRecord, ...]:
        return tuple(self._records.values())

    @property
    def interventions(self) -> tuple[Intervention, ...]:
        return tuple(self._interventions)

    def write(
        self,
        content: str,
        *,
        kind: MemoryKind = MemoryKind.KNOWLEDGE,
        tags: Iterable[str] = (),
        importance: float = 0.5,
        step: int = 0,
        memory_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> str:
        content = content.strip()
        if not content:
            raise ValueError("memory content must not be empty")
        if not 0 <= importance <= 1:
            raise ValueError("importance must be between 0 and 1")
        if step < 0:
            raise ValueError("step must be non-negative")
        normalized_tags = tuple(sorted({self._normalize_token(tag) for tag in tags if tag}))
        record_id = memory_id or self._make_id(kind, content)
        existing = self._records.get(record_id)
        if existing is not None:
            existing.content = content
            existing.kind = kind
            existing.tags = normalized_tags
            existing.importance = importance
            existing.stale = False
            existing.metadata = dict(metadata or existing.metadata)
            return record_id
        self._records[record_id] = MemoryRecord(
            memory_id=record_id,
            content=content,
            kind=kind,
            tags=normalized_tags,
            importance=importance,
            created_step=step,
            metadata=dict(metadata or {}),
        )
        self._evict_if_needed()
        return record_id

    def revise(
        self,
        memory_id: str,
        content: str,
        *,
        importance: Optional[float] = None,
        tags: Optional[Iterable[str]] = None,
        step: Optional[int] = None,
    ) -> None:
        record = self._records.get(memory_id)
        if record is None:
            raise KeyError(memory_id)
        content = content.strip()
        if not content:
            raise ValueError("memory content must not be empty")
        if importance is not None and not 0 <= importance <= 1:
            raise ValueError("importance must be between 0 and 1")
        if step is not None and step < 0:
            raise ValueError("step must be non-negative")
        record.content = content
        if importance is not None:
            record.importance = importance
        if tags is not None:
            record.tags = tuple(sorted({self._normalize_token(tag) for tag in tags if tag}))
        record.stale = False

    def mark_stale(self, memory_id: str, stale: bool = True) -> None:
        record = self._records.get(memory_id)
        if record is None:
            raise KeyError(memory_id)
        record.stale = stale

    def intervene(
        self,
        context: str,
        *,
        step: int,
        triggers: Iterable[MemoryTrigger | str] = (),
    ) -> Optional[Intervention]:
        if step < 0:
            raise ValueError("step must be non-negative")
        trigger_values = self._normalize_triggers(triggers)
        context_tokens = self._tokens(context)
        candidates: list[tuple[float, MemoryRecord, Optional[MemoryTrigger], str]] = []
        for record in self._records.values():
            if record.stale or self._in_cooldown(record, step):
                continue
            lexical = self._lexical_score(record, context_tokens)
            trigger, trigger_score = self._trigger_match(record, trigger_values)
            score = self._weighted_score(lexical, record.importance, trigger_score)
            if score < self.config.min_score:
                continue
            reason = self._reason(record, trigger, lexical, trigger_score)
            candidates.append((score, record, trigger, reason))
        candidates.sort(key=lambda item: (-item[0], -item[1].importance, item[1].memory_id))
        if not candidates:
            return None
        score, record, trigger, reason = candidates[0]
        intervention = Intervention(
            memory_id=record.memory_id,
            content=record.content,
            reason=reason,
            score=round(score, 6),
            step=step,
            trigger=trigger,
        )
        record.last_recalled_step = step
        record.recall_count += 1
        self._interventions.append(intervention)
        if len(self._interventions) > self.config.max_interventions:
            self._interventions = self._interventions[-self.config.max_interventions :]
        return intervention

    def run_step(
        self,
        context: str,
        *,
        step: int,
        writes: Iterable[Mapping[str, Any] | str] = (),
        triggers: Iterable[MemoryTrigger | str] = (),
    ) -> Optional[Intervention]:
        for item in writes:
            if isinstance(item, str):
                self.write(item, step=step)
            else:
                self.write(step=step, **dict(item))
        return self.intervene(context, step=step, triggers=triggers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": asdict(self.config),
            "records": [record.to_dict() for record in self._records.values()],
            "interventions": [item.to_dict() for item in self._interventions],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProactiveMemoryAgent":
        agent = cls(ProactiveMemoryConfig(**dict(data.get("config", {}))))
        for item in data.get("records", []):
            record = MemoryRecord.from_dict(item)
            agent._records[record.memory_id] = record
        for item in data.get("interventions", []):
            trigger = item.get("trigger")
            agent._interventions.append(
                Intervention(
                    memory_id=str(item["memory_id"]),
                    content=str(item["content"]),
                    reason=str(item["reason"]),
                    score=float(item["score"]),
                    step=int(item["step"]),
                    trigger=MemoryTrigger(trigger) if trigger else None,
                )
            )
        agent._interventions = agent._interventions[-agent.config.max_interventions :]
        agent._evict_if_needed()
        return agent

    def _evict_if_needed(self) -> None:
        while len(self._records) > self.config.max_records:
            victim = min(
                self._records.values(),
                key=lambda record: (
                    record.importance,
                    record.recall_count,
                    record.last_recalled_step if record.last_recalled_step is not None else -1,
                    record.memory_id,
                ),
            )
            del self._records[victim.memory_id]

    def _in_cooldown(self, record: MemoryRecord, step: int) -> bool:
        return (
            record.last_recalled_step is not None
            and step - record.last_recalled_step < self.config.cooldown_steps
        )

    def _lexical_score(self, record: MemoryRecord, context_tokens: set[str]) -> float:
        if not context_tokens:
            return 0.0
        record_tokens = self._tokens(record.content) | set(record.tags)
        return len(record_tokens & context_tokens) / len(context_tokens)

    def _trigger_match(
        self,
        record: MemoryRecord,
        triggers: set[MemoryTrigger],
    ) -> tuple[Optional[MemoryTrigger], float]:
        if not triggers:
            return None, 0.0
        record_tags = set(record.tags)
        matches = [trigger for trigger in triggers if trigger.value in record_tags]
        if matches:
            return sorted(matches, key=lambda trigger: trigger.value)[0], 1.0
        if record.kind == MemoryKind.PROCEDURAL and MemoryTrigger.ERROR in triggers:
            return MemoryTrigger.ERROR, 0.65
        if record.kind == MemoryKind.STATUS and MemoryTrigger.CONTEXT_SHIFT in triggers:
            return MemoryTrigger.CONTEXT_SHIFT, 0.65
        return None, 0.0

    def _weighted_score(self, lexical: float, importance: float, trigger: float) -> float:
        total = self.config.lexical_weight + self.config.importance_weight + self.config.trigger_weight
        return (
            self.config.lexical_weight * lexical
            + self.config.importance_weight * importance
            + self.config.trigger_weight * trigger
        ) / total

    def _reason(
        self,
        record: MemoryRecord,
        trigger: Optional[MemoryTrigger],
        lexical: float,
        trigger_score: float,
    ) -> str:
        if trigger is not None and trigger_score > 0:
            return f"{trigger.value} trigger matched {record.kind.value} memory"
        if lexical > 0:
            return "context overlap made memory decision-relevant"
        return "high-importance memory crossed intervention threshold"

    @staticmethod
    def _normalize_triggers(triggers: Iterable[MemoryTrigger | str]) -> set[MemoryTrigger]:
        result: set[MemoryTrigger] = set()
        for trigger in triggers:
            result.add(trigger if isinstance(trigger, MemoryTrigger) else MemoryTrigger(trigger))
        return result

    @staticmethod
    def _normalize_token(value: str) -> str:
        return re.sub(r"[^a-z0-9_]+", "", value.lower())

    @classmethod
    def _tokens(cls, value: str) -> set[str]:
        return {token for token in (cls._normalize_token(part) for part in value.split()) if len(token) > 2}

    @staticmethod
    def _make_id(kind: MemoryKind, content: str) -> str:
        digest = hashlib.sha256(f"{kind.value}:{content}".encode()).hexdigest()[:16]
        return f"mem_{digest}"


__all__ = [
    "Intervention",
    "MemoryKind",
    "MemoryRecord",
    "MemoryTrigger",
    "ProactiveMemoryAgent",
    "ProactiveMemoryConfig",
]
