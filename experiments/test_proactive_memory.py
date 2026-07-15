import json

import pytest

from core.proactive_memory import (
    MemoryKind,
    MemoryTrigger,
    ProactiveMemoryAgent,
    ProactiveMemoryConfig,
)


def test_selective_intervention_prefers_context_relevant_memory():
    agent = ProactiveMemoryAgent()
    agent.write(
        "The deployment must use the staging database.",
        kind=MemoryKind.STATUS,
        tags=["requirement"],
        importance=0.9,
        step=0,
    )
    agent.write(
        "The UI uses a dark theme.",
        kind=MemoryKind.KNOWLEDGE,
        importance=0.4,
        step=0,
    )

    intervention = agent.intervene(
        "Before deploying, verify the staging database connection.",
        step=1,
        triggers=[MemoryTrigger.REQUIREMENT],
    )

    assert intervention is not None
    assert "staging database" in intervention.content
    assert intervention.trigger == MemoryTrigger.REQUIREMENT
    assert intervention.score >= agent.config.min_score


def test_silence_when_memory_is_stale_or_irrelevant():
    agent = ProactiveMemoryAgent()
    memory_id = agent.write("The preferred color is blue.", importance=0.2)
    agent.mark_stale(memory_id)

    assert agent.intervene("Run the migration tests.", step=1) is None


def test_cooldown_prevents_repeated_injection():
    agent = ProactiveMemoryAgent(ProactiveMemoryConfig(cooldown_steps=3))
    agent.write("Always run the migration tests before release.", importance=1.0)

    first = agent.intervene("Run migration tests before release.", step=1)
    second = agent.intervene("Run migration tests before release.", step=2)
    third = agent.intervene("Run migration tests before release.", step=4)

    assert first is not None
    assert second is None
    assert third is not None


def test_revision_clears_stale_flag_and_preserves_identity():
    agent = ProactiveMemoryAgent()
    memory_id = agent.write("Old constraint", tags=["requirement"])
    agent.mark_stale(memory_id)
    agent.revise(memory_id, "Updated constraint", importance=0.8)

    assert agent.records[0].memory_id == memory_id
    assert agent.records[0].content == "Updated constraint"
    assert agent.records[0].stale is False


def test_record_capacity_evicts_low_value_memory():
    agent = ProactiveMemoryAgent(ProactiveMemoryConfig(max_records=2))
    agent.write("low", importance=0.1)
    agent.write("high", importance=0.9)
    agent.write("medium", importance=0.5)

    assert {record.content for record in agent.records} == {"high", "medium"}


def test_round_trip_serialization():
    agent = ProactiveMemoryAgent()
    agent.write("A failed command was caused by a missing package.", kind=MemoryKind.PROCEDURAL, tags=["error"], importance=0.8, step=2)
    agent.intervene("The command failed again.", step=3, triggers=[MemoryTrigger.ERROR])

    restored = ProactiveMemoryAgent.from_dict(json.loads(json.dumps(agent.to_dict())))

    assert restored.to_dict() == agent.to_dict()


def test_invalid_configuration_and_inputs_are_rejected():
    with pytest.raises(ValueError):
        ProactiveMemoryConfig(min_score=2)
    agent = ProactiveMemoryAgent()
    with pytest.raises(ValueError):
        agent.write("", step=0)
    with pytest.raises(ValueError):
        agent.intervene("context", step=-1)
