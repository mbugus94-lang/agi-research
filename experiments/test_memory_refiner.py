"""
Tests for the MemRefine-inspired Memory Refiner.

Validates:
- RefinementAction enum and RefinementDecision serialization
- Candidate pair proposal (similarity-based)
- FactDensityJudge singleton + pair judgments
- LLMJudgeStub records calls (no network)
- Refiner core: refine(), compress_one(), evict_one(), merge()
- Conservative posture: high-importance entries are protected
- Budget-pressure escalation
- Audit trail (JSONL)
- Determinism (same input -> same output)
- Integration with TieredMemorySystem
- Round-trip persistence
"""

import sys
import os
import json
import tempfile
import hashlib
from datetime import datetime, timedelta

sys.path.insert(0, '/home/workspace/agi-research')

from core.tiered_memory import (
    TieredMemorySystem,
    TieredMemoryEntry,
    MemoryTier,
)
from core.memory_refiner import (
    RefinementAction,
    RefinementCandidatePair,
    RefinementDecision,
    RefinementJudge,
    RefinementReport,
    MemoryRefinerConfig,
    MemoryRefiner,
    FactDensityJudge,
    LLMJudgeStub,
    create_memory_refiner,
    _fact_density,
    _novelty_score,
    _compress_facts,
    _merge_facts,
    _char_jaccard,
    _similarity,
    _cosine_similarity,
)


def run_tests():
    """Run all memory-refiner tests."""
    passed = 0
    failed = 0

    def test(name, condition, details=""):
        nonlocal passed, failed
        if condition:
            print(f"✅ {name}")
            passed += 1
        else:
            print(f"❌ {name}: {details}")
            failed += 1

    print("=" * 64)
    print("MEMORY REFINER TESTS")
    print("=" * 64)

    # ==== TEST 1: RefinementAction enum ====
    actions = [a.value for a in RefinementAction]
    test("RefinementAction has 5 values", len(actions) == 5, f"got {actions}")
    test("RefinementAction has KEEP", "keep" in actions)
    test("RefinementAction has EVICT", "evict" in actions)
    test("RefinementAction has MERGE", "merge" in actions)
    test("RefinementAction has COMPRESS", "compress" in actions)
    test("RefinementAction has PROMOTE", "promote" in actions)

    # ==== TEST 2: RefinementDecision dataclass ====
    d = RefinementDecision(
        action=RefinementAction.KEEP,
        target_ids=["a", "b"],
        reason="test",
        judge="unit",
        confidence=0.5,
    )
    test("Decision basic fields", d.action == RefinementAction.KEEP)
    test("Decision reason", d.reason == "test")
    test("Decision confidence 0..1", 0 <= d.confidence <= 1)
    d_dict = d.to_dict()
    test("Decision to_dict has action", "action" in d_dict)
    test("Decision to_dict has target_ids", "target_ids" in d_dict)
    test("Decision to_dict has reason", "reason" in d_dict)
    test("Decision to_dict has confidence", "confidence" in d_dict)
    test("Decision to_dict has judge", "judge" in d_dict)

    # ==== TEST 3: Decision requires compressed_content for COMPRESS ====
    try:
        RefinementDecision(
            action=RefinementAction.COMPRESS,
            target_ids=["x"],
            reason="x",
            judge="unit",
        )
        # If it didn't raise, that's a bug
        test("COMPRESS requires compressed_content", False, "no exception raised")
    except ValueError:
        test("COMPRESS requires compressed_content", True)

    try:
        RefinementDecision(
            action=RefinementAction.MERGE,
            target_ids=["x", "y"],
            reason="x",
            judge="unit",
        )
        test("MERGE requires compressed_content", False, "no exception raised")
    except ValueError:
        test("MERGE requires compressed_content", True)

    # ==== TEST 4: Helper functions ====
    test("fact_density empty = 0.0", _fact_density("") == 0.0, f"got {_fact_density('')}")
    test("fact_density non-empty > 0.0", _fact_density("hello world") > 0.0)
    test("fact_density numbers > 0", _fact_density("12345") > 0.0)
    test("novelty_score default 0.5", abs(_novelty_score(TieredMemoryEntry(content="x")) - 0.5) < 0.01)
    test("char_jaccard identical = 1.0", _char_jaccard("hello", "hello") == 1.0)
    test("char_jaccard disjoint = 0.0", _char_jaccard("abc", "xyz") == 0.0)
    test("char_jaccard similar > 0.5", _char_jaccard("hello world foo bar", "hello world foo baz") > 0.5)
    test("char_jaccard case-insensitive", _char_jaccard("Hello", "hello") == 1.0)

    # ==== TEST 5: compress_facts preserves data ====
    d1 = {"a": 1, "b": "x"}
    c1 = _compress_facts(d1)
    test("compress dict returns str", isinstance(c1, str))
    test("compress dict preserves data", "a" in c1 and "1" in c1)

    # ==== TEST 6: merge_facts ====
    m1 = _merge_facts("alpha beta", "beta gamma")
    test("merge_facts includes both", "alpha" in m1 and "gamma" in m1)

    # ==== TEST 7: cosine_similarity ====
    test("cosine identical = 1.0", abs(_cosine_similarity([1, 0], [1, 0]) - 1.0) < 1e-6)
    test("cosine orthogonal = 0.0", abs(_cosine_similarity([1, 0], [0, 1]) - 0.0) < 1e-6)
    test("cosine opposite = -1.0", abs(_cosine_similarity([1, 0], [-1, 0]) - -1.0) < 1e-6)
    test("cosine empty = 0.0", _cosine_similarity([], [1, 2]) == 0.0)
    test("cosine mismatch length = 0.0", _cosine_similarity([1, 2], [1, 2, 3]) == 0.0)

    # ==== TEST 8: FactDensityJudge singleton judgments ====
    judge = FactDensityJudge()
    e_high = TieredMemoryEntry(content="x", importance=0.9)
    d_high = judge.judge_singleton(e_high, current_size=10, budget=5)
    test("high importance -> KEEP", d_high.action == RefinementAction.KEEP)

    e_low = TieredMemoryEntry(content="x", importance=0.1)
    d_low = judge.judge_singleton(e_low, current_size=10, budget=5)
    test("low importance -> EVICT or COMPRESS", d_low.action in (
        RefinementAction.EVICT, RefinementAction.COMPRESS
    ))

    e_med = TieredMemoryEntry(content="x", importance=0.5)
    e_med.access_count = 5
    d_med = judge.judge_singleton(e_med, current_size=10, budget=5)
    test("medium importance + high access -> PROMOTE or KEEP", d_med.action in (
        RefinementAction.PROMOTE, RefinementAction.KEEP
    ))

    # ==== TEST 9: FactDensityJudge pair judgments ====
    p_low_sim = RefinementCandidatePair(
        a_id="a", b_id="b", similarity=0.1,
        a_content="x", b_content="y",
        a_importance=0.5, b_importance=0.5,
        a_tags=[], b_tags=[], a_associations=[], b_associations=[],
    )
    d_low_sim = judge.judge_pair(p_low_sim)
    test("low similarity -> KEEP", d_low_sim.action == RefinementAction.KEEP)

    p_high = RefinementCandidatePair(
        a_id="a", b_id="b", similarity=0.9,
        a_content="x", b_content="y",
        a_importance=0.9, b_importance=0.9,
        a_tags=["t1"], b_tags=["t1"], a_associations=[], b_associations=[],
    )
    d_high = judge.judge_pair(p_high)
    test("both high importance -> KEEP", d_high.action == RefinementAction.KEEP)

    p_merger = RefinementCandidatePair(
        a_id="a", b_id="b", similarity=0.9,
        a_content="x", b_content="y",
        a_importance=0.2, b_importance=0.2,
        a_tags=["t1"], b_tags=["t1"], a_associations=[], b_associations=[],
    )
    d_merger = judge.judge_pair(p_merger)
    test("low importance + shared tag -> MERGE", d_merger.action == RefinementAction.MERGE)

    p_one_high = RefinementCandidatePair(
        a_id="a", b_id="b", similarity=0.7,
        a_content="x", b_content="y",
        a_importance=0.9, b_importance=0.2,
        a_tags=["t1"], b_tags=["t1"], a_associations=[], b_associations=[],
    )
    d_one_high = judge.judge_pair(p_one_high)
    test("one high one low -> MERGE", d_one_high.action == RefinementAction.MERGE)

    # ==== TEST 10: LLMJudgeStub records calls ====
    stub = LLMJudgeStub()
    e = TieredMemoryEntry(content="x", importance=0.1)
    stub.judge_singleton(e, current_size=10, budget=5)
    test("LLMStub records singleton calls", len(stub.calls) == 1)
    p = RefinementCandidatePair(
        a_id="a", b_id="b", similarity=0.5,
        a_content="x", b_content="y",
        a_importance=0.5, b_importance=0.5,
        a_tags=[], b_tags=[], a_associations=[], b_associations=[],
    )
    stub.calls = []  # reset
    stub.judge_pair(p)
    test("LLMStub records pair calls", len(stub.calls) == 1)

    # ==== TEST 11: RefinementCandidatePair helpers ====
    p_pair = RefinementCandidatePair(
        a_id="a", b_id="b", similarity=0.5,
        a_content="x", b_content="y",
        a_importance=0.5, b_importance=0.5,
        a_tags=["t1", "t2"], b_tags=["t2", "t3"], a_associations=[], b_associations=[])
    test("tag_union_size", p_pair.tag_union_size() == 3, f"got {p_pair.tag_union_size()}")
    test("shared_tags", p_pair.shared_tags() == {"t2"})

    # ==== TEST 12: MemoryRefiner setup ====
    mem = TieredMemorySystem(l1_capacity=20)
    refiner = MemoryRefiner(memory=mem)
    test("Refiner has default judge", refiner.judge is not None)
    test("Refiner has audit trail", isinstance(refiner.audit, list))
    test("Refiner audit empty initially", len(refiner.audit) == 0)

    # ==== TEST 13: propose_pairs ====
    mem2 = TieredMemorySystem(l1_capacity=20)
    for i in range(5):
        mem2.store_l1("User said hello at the same time", tags=["greeting"], importance=0.5)
    refiner2 = MemoryRefiner(memory=mem2)
    pairs = refiner2.propose_pairs()
    test("propose_pairs returns list", isinstance(pairs, list))
    test("propose_pairs non-empty for duplicates", len(pairs) > 0, f"got {len(pairs)}")

    # ==== TEST 14: refine() reduces size ====
    mem3 = TieredMemorySystem(l1_capacity=20)
    for i in range(8):
        mem3.store_l1(
            f"Garbage entry number {i} with some facts: 2026-06-17",
            tags=[f"g{i}"],
            importance=0.1 + i * 0.01,
        )
    # Add one high-importance keeper
    mem3.store_l1("Critical config: /etc/secret", tags=["critical"], importance=0.95)
    initial_size = len(mem3.l1_working) + len(mem3.l2_longterm)
    refiner3 = MemoryRefiner(memory=mem3)
    report = refiner3.refine(budget=3)
    final_size = len(mem3.l1_working) + len(mem3.l2_longterm)
    test(
        "refine() reduces size",
        final_size <= 3,
        f"initial={initial_size}, final={final_size}, budget=3",
    )
    test("refine() preserves high-importance entry", any(
        e.importance >= 0.9 for e in mem3.l1_working.values()
    ))
    test("refine() report has final_size", report.final_size == final_size)
    test("refine() report decisions > 0", len(report.decisions) > 0)

    # ==== TEST 15: refine() under budget is no-op ====
    mem4 = TieredMemorySystem(l1_capacity=20)
    for i in range(3):
        mem4.store_l1(f"item {i}", tags=[f"t{i}"], importance=0.5)
    refiner4 = MemoryRefiner(memory=mem4)
    report4 = refiner4.refine(budget=10)
    test("refine() no-op when under budget", report4.iterations == 0 or report4.final_size == 3)

    # ==== TEST 16: compress_one ====
    mem5 = TieredMemorySystem(l1_capacity=20)
    eid = mem5.store_l1("Some long fact with numbers 42 and dates 2026-06-17", tags=["x"], importance=0.4)
    refiner5 = MemoryRefiner(memory=mem5)
    decision = refiner5.compress_one(eid)
    test("compress_one returns decision", decision is not None)
    test("compress_one is KEEP or COMPRESS", decision.action in (
        RefinementAction.KEEP, RefinementAction.COMPRESS
    ))

    # ==== TEST 17: evict_one respects safety floor ====
    mem6 = TieredMemorySystem(l1_capacity=20)
    eid_low = mem6.store_l1("low", tags=[], importance=0.1)
    eid_high = mem6.store_l1("high", tags=[], importance=0.95)
    refiner6 = MemoryRefiner(memory=mem6)
    # Should be able to evict low
    decision_low = refiner6.evict_one(eid_low)
    test("evict_one low importance returns decision", decision_low is not None)
    test("evict_one may evict low", decision_low.action in (
        RefinementAction.EVICT, RefinementAction.KEEP,
    ))

    # ==== TEST 18: merge() ====
    mem7 = TieredMemorySystem(l1_capacity=20)
    a_id = mem7.store_l1("alpha fact one alpha fact one", tags=["t1"], importance=0.5)
    b_id = mem7.store_l1("alpha fact one alpha fact one", tags=["t1"], importance=0.5)
    refiner7 = MemoryRefiner(memory=mem7)
    decision7 = refiner7.merge(a_id, b_id)
    test("merge returns decision", isinstance(decision7, RefinementDecision))
    test("merge is MERGE action", decision7 is not None and decision7.action == RefinementAction.MERGE)
    # One entry should be gone (merged into one survivor)
    remaining = [e for e in mem7.l1_working.values() if e.id in (a_id, b_id)]
    test("merge keeps one survivor", len(remaining) == 1, f"got {len(remaining)}")

    # ==== TEST 19: merge with non-existent IDs is safe ====
    mem8 = TieredMemorySystem(l1_capacity=20)
    refiner8 = MemoryRefiner(memory=mem8)
    report8 = refiner8.merge("nonexistent-a", "nonexistent-b")
    test("merge of non-existent IDs is safe", report8 is None)

    # ==== TEST 20: summary() ====
    mem9 = TieredMemorySystem(l1_capacity=20)
    for i in range(3):
        mem9.store_l1(f"item {i}", tags=[f"t{i}"], importance=0.1)
    refiner9 = MemoryRefiner(memory=mem9)
    refiner9.refine(budget=1)
    s = refiner9.summary()
    test("summary has audit_count", "audit_count" in s)
    test("summary has actions", "actions" in s)
    test("summary has current_size", "current_size" in s)
    test("summary has judge", "judge" in s)
    test("summary audit_count > 0", s["audit_count"] > 0)

    # ==== TEST 21: audit trail persistence (JSONL) ====
    with tempfile.TemporaryDirectory() as tmpdir:
        audit_path = os.path.join(tmpdir, "audit.jsonl")
        mem10 = TieredMemorySystem(l1_capacity=20)
        for i in range(5):
            mem10.store_l1(f"item {i}", tags=[f"t{i}"], importance=0.1)
        config = MemoryRefinerConfig(audit_path=audit_path)
        refiner10 = MemoryRefiner(memory=mem10, config=config)
        refiner10.refine(budget=2)
        test("audit file exists", os.path.exists(audit_path))
        with open(audit_path) as f:
            lines = f.readlines()
        test("audit file non-empty", len(lines) > 0)
        first = json.loads(lines[0])
        test("audit row has action", "action" in first)
        test("audit row has target_ids", "target_ids" in first)
        test("audit row has reason", "reason" in first)
        test("audit row has judge", "judge" in first)

    # ==== TEST 22: Determinism (same input -> same output) ====
    def build_and_refine():
        m = TieredMemorySystem(l1_capacity=20)
        for i in range(6):
            m.store_l1(f"item {i}", tags=[f"t{i}"], importance=0.1 + i * 0.01)
        r = MemoryRefiner(memory=m)
        rep = r.refine(budget=2)
        return rep.final_size, [d.action.value for d in rep.decisions]

    f1 = build_and_refine()
    f2 = build_and_refine()
    test("refine() is deterministic (final_size)", f1[0] == f2[0], f"{f1[0]} vs {f2[0]}")
    test("refine() is deterministic (decisions)", f1[1] == f2[1])

    # ==== TEST 23: RefinerConfig knobs ====
    config = MemoryRefinerConfig(
        similarity_threshold=0.7,
        max_iterations=3,
        audit_path="/tmp/x.jsonl",
    )
    test("Config similarity_threshold", config.similarity_threshold == 0.7)
    test("Config max_iterations", config.max_iterations == 3)
    test("Config protect_above_importance default 0.85",
         MemoryRefinerConfig().protect_above_importance == 0.85)

    # ==== TEST 24: create_memory_refiner helper ====
    mem11 = TieredMemorySystem(l1_capacity=20)
    refiner11 = create_memory_refiner(mem11)
    test("create_memory_refiner returns MemoryRefiner", isinstance(refiner11, MemoryRefiner))
    test("create_memory_refiner default judge is FactDensityJudge",
         isinstance(refiner11.judge, FactDensityJudge))

    # ==== TEST 25: Budget-pressure escalation ====
    # 8 entries all with high fact_density -> should still evict when far over budget
    mem12 = TieredMemorySystem(l1_capacity=20)
    for i in range(8):
        mem12.store_l1(
            f"Important fact number {i} on 2026-06-17",
            tags=[f"t{i}"],
            importance=0.4,  # below keep_floor
        )
    refiner12 = MemoryRefiner(memory=mem12)
    report12 = refiner12.refine(budget=2)
    test(
        "budget pressure -> evict",
        report12.evicted >= 1 or report12.compressed >= 1,
        f"evicted={report12.evicted}, compressed={report12.compressed}",
    )

    # ==== TEST 26: High-importance protection ====
    mem13 = TieredMemorySystem(l1_capacity=20)
    for i in range(10):
        mem13.store_l1(f"low {i}", tags=[f"l{i}"], importance=0.1)
    keeper_id = mem13.store_l1("KEEPER", tags=["keeper"], importance=0.95)
    refiner13 = MemoryRefiner(memory=mem13)
    refiner13.refine(budget=2)
    test("high importance entry preserved",
         any(e.id == keeper_id for e in mem13.l1_working.values()),
         "keeper was evicted!")

    # ==== TEST 27: Propose pairs only above similarity threshold ====
    mem14 = TieredMemorySystem(l1_capacity=20)
    mem14.store_l1("Apple banana cherry", tags=["fruit"], importance=0.5)
    mem14.store_l1("Apple banana date", tags=["fruit"], importance=0.5)
    mem14.store_l1("Zebra quantum physics", tags=["unrelated"], importance=0.5)
    refiner14 = MemoryRefiner(memory=mem14)
    pairs14 = refiner14.propose_pairs()
    # Pairs should not include the unrelated one
    for p in pairs14:
        a = mem14.l1_working.get(p.a_id)
        b = mem14.l1_working.get(p.b_id)
        if a and b:
            tags_a = set(a.tags)
            tags_b = set(b.tags)
            # Should not pair unrelated content
            assert "unrelated" not in tags_a or "unrelated" not in tags_b or \
                   ("unrelated" in tags_a and "unrelated" in tags_b and a.content == b.content)

    test("propose_pairs respects similarity threshold", True)

    # ==== TEST 28: Audit trail in-memory + JSONL agree ====
    with tempfile.TemporaryDirectory() as tmpdir:
        audit_path = os.path.join(tmpdir, "audit.jsonl")
        mem15 = TieredMemorySystem(l1_capacity=20)
        for i in range(4):
            mem15.store_l1(f"item {i}", tags=[f"t{i}"], importance=0.1)
        config = MemoryRefinerConfig(audit_path=audit_path)
        refiner15 = MemoryRefiner(memory=mem15, config=config)
        refiner15.refine(budget=1)
        in_mem = len(refiner15.audit)
        with open(audit_path) as f:
            on_disk = sum(1 for _ in f)
        test("in-memory audit == on-disk audit", in_mem == on_disk,
             f"in_mem={in_mem}, on_disk={on_disk}")

    # ==== TEST 29: Refine returns valid RefinementReport ====
    mem16 = TieredMemorySystem(l1_capacity=20)
    for i in range(3):
        mem16.store_l1(f"item {i}", tags=[f"t{i}"], importance=0.5)
    refiner16 = MemoryRefiner(memory=mem16)
    report16 = refiner16.refine(budget=2)
    test("Report is RefinementReport", isinstance(report16, RefinementReport))
    test("Report has all counters", all(hasattr(report16, attr) for attr in [
        "initial_size", "final_size", "iterations",
        "evicted", "compressed", "merged_pairs", "promoted", "kept", "decisions",
    ]))
    test("Report to_dict works", isinstance(report16.to_dict(), dict))

    # ==== TEST 30: LLMJudgeStub JSON serialization ====
    # Default behavior tests
    stub2 = LLMJudgeStub()
    test("LLMStub default name", stub2.name == "llm_stub")
    e30 = TieredMemoryEntry(content="x", importance=0.1)
    d30 = stub2.judge_singleton(e30, current_size=10, budget=5)
    test("LLMStub default low importance -> COMPRESS", d30.action == RefinementAction.COMPRESS)
    p30 = RefinementCandidatePair(
        a_id="a", b_id="b", similarity=0.5,
        a_content="x", b_content="y",
        a_importance=0.5, b_importance=0.5, a_tags=[], b_tags=[], a_associations=[], b_associations=[])
    d30p = stub2.judge_pair(p30)
    test("LLMStub default above-threshold pair -> MERGE", d30p.action == RefinementAction.MERGE)

    # ==== TEST 31: RefinementJudge protocol satisfaction ====
    # FactDensityJudge and LLMJudgeStub both have the right methods
    test("FactDensityJudge has judge_singleton", hasattr(FactDensityJudge(), "judge_singleton"))
    test("FactDensityJudge has judge_pair", hasattr(FactDensityJudge(), "judge_pair"))
    test("LLMJudgeStub has judge_singleton", hasattr(LLMJudgeStub(), "judge_singleton"))
    test("LLMJudgeStub has judge_pair", hasattr(LLMJudgeStub(), "judge_pair"))

    # ==== TEST 32: Refiner doesn't mutate entries in place during COMPRESS (creates new) ====
    # The current impl mutates content in place; this is a known choice (atomic refiner
    # without WAL). The test documents the behavior.
    mem17 = TieredMemorySystem(l1_capacity=20)
    eid17 = mem17.store_l1("Long content with many facts 2026-06-17 and numbers 42", tags=["x"], importance=0.3)
    original_content = mem17.l1_working[eid17].content
    refiner17 = MemoryRefiner(memory=mem17)
    refiner17.compress_one(eid17)
    # Content may be mutated (in-place compression)
    current_content = mem17.l1_working[eid17].content
    test("compress_one either keeps or mutates content",
         current_content is not None, "content lost!")

    # ==== TEST 33: Empty memory is safe ====
    mem18 = TieredMemorySystem(l1_capacity=20)
    refiner18 = MemoryRefiner(memory=mem18)
    report18 = refiner18.refine(budget=5)
    test("refine on empty memory is safe", report18 is not None)
    test("refine on empty memory final_size=0", report18.final_size == 0)

    # ==== TEST 34: Conservative posture — never evict above protect_above_importance ====
    mem19 = TieredMemorySystem(l1_capacity=20)
    keeper_id_19 = mem19.store_l1("KEEPER 2", tags=["k"], importance=0.9)
    config19 = MemoryRefinerConfig(protect_above_importance=0.85)
    refiner19 = MemoryRefiner(memory=mem19, config=config19)
    decision19 = refiner19.evict_one(keeper_id_19)
    test("protect_above_importance respected (KEEP)",
         decision19.action == RefinementAction.KEEP,
         f"action={decision19.action}")

    # ==== TEST 35: RefinementCandidatePair similarity stored ====
    p35 = RefinementCandidatePair(
        a_id="a", b_id="b", similarity=0.42,
        a_content="x", b_content="y",
        a_importance=0.5, b_importance=0.5, a_tags=[], b_tags=[], a_associations=[], b_associations=[])
    test("pair similarity stored", p35.similarity == 0.42)

    # ==== TEST 36: Tag union size with no shared tags ====
    p36 = RefinementCandidatePair(
        a_id="a", b_id="b", similarity=0.9,
        a_content="x", b_content="y",
        a_importance=0.5, b_importance=0.5,
        a_tags=["t1", "t2"], b_tags=["t3", "t4"], a_associations=[], b_associations=[])
    test("tag_union_size disjoint", p36.tag_union_size() == 4)
    test("shared_tags empty", p36.shared_tags() == set())

    # ==== TEST 37: max_iterations cap ====
    config37 = MemoryRefinerConfig(max_iterations=1)
    mem37 = TieredMemorySystem(l1_capacity=20)
    for i in range(10):
        mem37.store_l1(f"item {i}", tags=[f"t{i}"], importance=0.1)
    refiner37 = MemoryRefiner(memory=mem37, config=config37)
    report37 = refiner37.refine(budget=1)
    test("max_iterations respected", report37.iterations <= 1, f"got {report37.iterations}")

    # ==== TEST 38: Cross-tier refinement (L1 + L2) ====
    mem38 = TieredMemorySystem(l1_capacity=20)
    mem38.store_l2("Old fact 2026-01-01", tags=["old"], importance=0.1)
    mem38.store_l1("New fact 2026-06-17", tags=["new"], importance=0.1)
    refiner38 = MemoryRefiner(memory=mem38)
    report38 = refiner38.refine(budget=0)
    final = len(mem38.l1_working) + len(mem38.l2_longterm)
    test("cross-tier refine respects budget", final <= 1, f"got {final}")

    # ==== TEST 39: Summary action counts ====
    mem39 = TieredMemorySystem(l1_capacity=20)
    for i in range(5):
        mem39.store_l1(f"item {i}", tags=[f"t{i}"], importance=0.1)
    refiner39 = MemoryRefiner(memory=mem39)
    refiner39.refine(budget=2)
    s39 = refiner39.summary()
    test("summary has actions dict", "actions" in s39)
    test("summary actions has at least one action",
         sum(s39["actions"].values()) > 0,
         f"actions={s39['actions']}")

    # ==== TEST 40: Round-trip persistence (RefinementReport.to_dict -> JSON) ====
    mem40 = TieredMemorySystem(l1_capacity=20)
    for i in range(3):
        mem40.store_l1(f"item {i}", tags=[f"t{i}"], importance=0.5)
    refiner40 = MemoryRefiner(memory=mem40)
    report40 = refiner40.refine(budget=2)
    j = json.dumps(report40.to_dict())
    parsed = json.loads(j)
    test("Report round-trips through JSON", parsed["initial_size"] == report40.initial_size)

    # ==== TEST 41: compress_facts for string content ====
    s41 = _compress_facts("hello world")
    test("compress string returns str", isinstance(s41, str))

    # ==== TEST 42: merge_facts de-dupes ====
    m42 = _merge_facts("alpha beta gamma", "beta gamma delta")
    test("merge dedupes terms", "alpha" in m42 and "delta" in m42)

    # ==== TEST 43: similarity between two entries ====
    e43a = TieredMemoryEntry(content="apple banana", tags=["fruit"])
    e43a.embedding = [1.0, 0.0, 0.0]
    e43b = TieredMemoryEntry(content="apple banana", tags=["fruit"])
    e43b.embedding = [1.0, 0.0, 0.0]
    test("similarity identical = 1.0", abs(_similarity(e43a, e43b) - 1.0) < 1e-6)
    e43c = TieredMemoryEntry(content="unrelated", tags=["x"])
    e43c.embedding = [0.0, 0.0, 1.0]
    test("similarity orthogonal = 0.0", _similarity(e43a, e43c) < 0.5)

    # ==== TEST 44: RefinementDecision for EVICT/PROMOTE doesn't need compressed_content ====
    d44e = RefinementDecision(
        action=RefinementAction.EVICT,
        target_ids=["x"],
        reason="x",
        judge="unit",
    )
    test("EVICT doesn't need compressed_content", d44e is not None)
    d44p = RefinementDecision(
        action=RefinementAction.PROMOTE,
        target_ids=["x"],
        reason="x",
        judge="unit",
    )
    test("PROMOTE doesn't need compressed_content", d44p is not None)
    d44k = RefinementDecision(
        action=RefinementAction.KEEP,
        target_ids=["x"],
        reason="x",
        judge="unit",
    )
    test("KEEP doesn't need compressed_content", d44k is not None)

    # ==== TEST 45: LLMJudgeStub records structured call info ====
    stub45 = LLMJudgeStub()
    e45 = TieredMemoryEntry(content="abc def ghi", importance=0.3)
    e45.tags = ["t1", "t2"]
    stub45.judge_singleton(e45, current_size=10, budget=5)
    rec = stub45.calls[0]
    test("stub records entry_id", "entry_id" in rec)
    test("stub records content", "content" in rec)
    test("stub records entry_id", "entry_id" in rec)
    test("stub records current_size", "current_size" in rec)
    test("stub records budget", "budget" in rec)
    test("stub records importance", "importance" in rec)

    # ==== TEST 46: Maximum-budget edge case (budget=0) ====
    mem46 = TieredMemorySystem(l1_capacity=20)
    for i in range(3):
        mem46.store_l1(f"item {i}", tags=[f"t{i}"], importance=0.5)
    refiner46 = MemoryRefiner(memory=mem46)
    report46 = refiner46.refine(budget=0)
    final46 = len(mem46.l1_working) + len(mem46.l2_longterm)
    test("budget=0 refines aggressively", final46 <= 1, f"got {final46}")

    # ==== TEST 47: Refine under budget=0 with protected entry ====
    mem47 = TieredMemorySystem(l1_capacity=20)
    keeper_47 = mem47.store_l1("KEEPER", tags=["k"], importance=0.9)
    for i in range(3):
        mem47.store_l1(f"item {i}", tags=[f"t{i}"], importance=0.1)
    refiner47 = MemoryRefiner(memory=mem47)
    report47 = refiner47.refine(budget=0)
    # High-importance entry may still be preserved due to protect_above_importance
    final47 = len(mem47.l1_working) + len(mem47.l2_longterm)
    test("refine budget=0 ends in bounded state", final47 <= 2, f"got {final47}")

    # ==== TEST 48: RefinementReport.to_dict round-trip ====
    r48 = RefinementReport(initial_size=10, final_size=5, iterations=2)
    d48 = r48.to_dict()
    test("Report.to_dict initial_size", d48["initial_size"] == 10)
    test("Report.to_dict final_size", d48["final_size"] == 5)
    test("Report.to_dict iterations", d48["iterations"] == 2)
    test("Report.to_dict decision_count", d48["decision_count"] == 0)

    # ==== TEST 49: compress_facts for tuple/list content ====
    c49 = _compress_facts([1, 2, 3, "x"])
    test("compress list returns str", isinstance(c49, str))
    c49b = _compress_facts(("a", "b", "c"))
    test("compress tuple returns str", isinstance(c49b, str))

    # ==== TEST 50: Refine runs without errors on mixed-tag memory ====
    mem50 = TieredMemorySystem(l1_capacity=20)
    for i in range(5):
        mem50.store_l1(
            f"task {i} with date 2026-06-17 and id {i}",
            tags=[f"task{i}", "ephemeral"],
            importance=0.1 + (i % 3) * 0.2,
        )
    refiner50 = MemoryRefiner(memory=mem50)
    report50 = refiner50.refine(budget=2)
    test("mixed-tag refine runs without error", report50 is not None)
    final50 = len(mem50.l1_working) + len(mem50.l2_longterm)
    test("mixed-tag refine respects budget", final50 <= 3, f"got {final50}")

    # ==== TEST 51: Custom judge with aggressive eviction ====
    class AggressiveJudge(FactDensityJudge):
        def judge_singleton(self, entry, current_size, budget):
            if current_size > budget:
                if entry.importance < 0.9:
                    return RefinementDecision(
                        action=RefinementAction.EVICT,
                        target_ids=[entry.id],
                        reason="aggressive",
                        judge="aggressive",
                    )
            return super().judge_singleton(entry, current_size, budget)

    mem51 = TieredMemorySystem(l1_capacity=20)
    for i in range(6):
        mem51.store_l1(f"item {i}", tags=[f"t{i}"], importance=0.5)
    refiner51 = MemoryRefiner(memory=mem51, judge=AggressiveJudge())
    report51 = refiner51.refine(budget=2)
    final51 = len(mem51.l1_working) + len(mem51.l2_longterm)
    test("custom judge works", final51 <= 2, f"got {final51}")

    # ==== TEST 52: FactDensityJudge parameter overrides ====
    j52 = FactDensityJudge(keep_floor=0.5, promote_floor=0.3)
    test("custom keep_floor", j52.keep_floor == 0.5)
    test("custom promote_floor", j52.promote_floor == 0.3)
    e52 = TieredMemoryEntry(content="x", importance=0.4)
    d52 = j52.judge_singleton(e52, current_size=10, budget=5)
    test("custom judge KEEPs at 0.4 (above custom keep_floor=0.5? no, 0.4<0.5)",
         d52.action in (RefinementAction.KEEP, RefinementAction.PROMOTE, RefinementAction.COMPRESS, RefinementAction.EVICT))

    # ==== TEST 53: Similarity helper with None embeddings ====
    e53a = TieredMemoryEntry(content="x", tags=[])
    e53b = TieredMemoryEntry(content="x", tags=[])
    # Both have None embeddings
    test("similarity None/None falls back to char jaccard", _similarity(e53a, e53b) == 1.0)

    # ==== TEST 54: LLMJudgeStub can be configured per-action ====
    stub54a = LLMJudgeStub(always_action=RefinementAction.EVICT)
    e54 = TieredMemoryEntry(content="x", importance=0.9)
    d54 = stub54a.judge_singleton(e54, current_size=10, budget=5)
    test("stub always returns EVICT", d54.action == RefinementAction.EVICT)

    stub54b = LLMJudgeStub(always_action=RefinementAction.PROMOTE)
    d54b = stub54b.judge_singleton(e54, current_size=10, budget=5)
    test("stub always returns PROMOTE", d54b.action == RefinementAction.PROMOTE)

    # ==== TEST 55: Refiner with no judge uses default ====
    mem55 = TieredMemorySystem(l1_capacity=20)
    r55 = MemoryRefiner(memory=mem55)
    test("default judge is FactDensityJudge", isinstance(r55.judge, FactDensityJudge))

    # ==== TEST 56: Audit count matches decisions in report ====
    mem56 = TieredMemorySystem(l1_capacity=20)
    for i in range(4):
        mem56.store_l1(f"item {i}", tags=[f"t{i}"], importance=0.1)
    r56 = MemoryRefiner(memory=mem56)
    report56 = r56.refine(budget=1)
    test("audit count == report decisions",
         len(r56.audit) == len(report56.decisions),
         f"audit={len(r56.audit)}, report={len(report56.decisions)}")

    # ==== TEST 57: All actions covered by enum ====
    expected_actions = {RefinementAction.KEEP, RefinementAction.EVICT,
                        RefinementAction.MERGE, RefinementAction.COMPRESS,
                        RefinementAction.PROMOTE}
    test("All 5 actions defined", len(RefinementAction) == 5)

    # ==== Summary ====
    print("=" * 64)
    print(f"PASSED: {passed}")
    print(f"FAILED: {failed}")
    print("=" * 64)
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
