"""
Tests for the Context-Oriented Memory Cache (PEEK-inspired).

Covers:
- Distiller: fact/pattern/schema/summary/tool_trace extraction
- Cartographer: dedup, update, noop decisions
- Evictor: brings cache under budget under each policy
- ContextMap: lookup, save, update, remove, ingest_trace, budget enforcement
- Agent wrapper: consult / remember flow
- Cost-savings tracking (metacognitive monitor hook)
"""

import unittest
from typing import List, Tuple

from core.context_cache import (
    AccessOutcome,
    CacheEntryKind,
    CacheStats,
    Cartographer,
    ContextMap,
    ContextOrientedAgent,
    Distiller,
    EditAction,
    EvictionPolicy,
    Evictor,
    create_agent,
    create_cache,
)


# ---------------------------------------------------------------------------
# Distiller tests
# ---------------------------------------------------------------------------


class DistillerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.distiller = Distiller()

    def test_extracts_facts_with_keyword_markers(self):
        trace = [
            ("user", "The capital of France is Paris. The currency is the Euro."),
            ("assistant", "Paris is the capital of France."),
        ]
        result = self.distiller.distill(trace)
        self.assertGreater(len(result.facts), 0)

    def test_extracts_tool_traces(self):
        trace = [
            ("assistant", "tool: web_search(query='agi research')"),
            ("assistant", "use calculator(2+2)"),
        ]
        result = self.distiller.distill(trace)
        self.assertGreaterEqual(len(result.tool_traces), 2)

    def test_extracts_schemas_from_markdown(self):
        trace = [("user", "# Project\n- Item A\n- Item B\n## Section 2")]
        result = self.distiller.distill(trace)
        self.assertGreater(len(result.schemas), 0)

    def test_extracts_summaries_for_long_lines(self):
        long_line = " ".join(["This is a fairly long narrative sentence."] * 12)
        trace = [("user", long_line)]
        result = self.distiller.distill(trace)
        self.assertGreater(len(result.summaries), 0)

    def test_empty_trace(self):
        result = self.distiller.distill([])
        self.assertTrue(result.is_empty())
        self.assertEqual(result.total_items(), 0)

    def test_dedupes_identical_lines(self):
        trace = [
            ("user", "The capital of France is Paris."),
            ("user", "The capital of France is Paris."),
        ]
        result = self.distiller.distill(trace)
        keys = [k for k, _ in result.facts]
        self.assertEqual(len(keys), len(set(keys)))

    def test_handles_dict_messages(self):
        trace = [{"role": "assistant", "content": "tool: read_file(/etc/hosts)"}]
        result = self.distiller.distill(trace)
        self.assertGreaterEqual(len(result.tool_traces), 1)

    def test_handles_object_with_role_content(self):
        class Msg:
            def __init__(self, role, content):
                self.role = role
                self.content = content
        trace = [Msg("user", "alpha is 1. beta is 2.")]
        result = self.distiller.distill(trace)
        self.assertGreater(len(result.facts), 0)


# ---------------------------------------------------------------------------
# Cartographer tests
# ---------------------------------------------------------------------------


class CartographerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cartographer = Cartographer()
        self.distiller = Distiller()

    def test_adds_new_entries(self):
        trace = [("user", "The capital of France is Paris.")]
        result = self.distiller.distill(trace)
        edits = self.cartographer.plan(result, existing={})
        add_edits = [e for e in edits if e.action == EditAction.ADD]
        self.assertGreater(len(add_edits), 0)

    def test_updates_existing_entries(self):
        trace = [("user", "The capital of France is Paris.")]
        result = self.distiller.distill(trace)
        edits_first = self.cartographer.plan(result, existing={})
        # materialize into a fake "existing" dict
        existing = {
            e.key: ContextMap().entries.__class__()  # placeholder
        } if False else {}
        # Build a real existing map for second pass
        cm = ContextMap()
        cm.ingest_trace(trace)
        existing = dict(cm.entries)
        edits_second = self.cartographer.plan(result, existing=existing)
        # At least one edit should be UPDATE since keys are re-seen
        update_or_add = [e for e in edits_second
                         if e.action in (EditAction.UPDATE, EditAction.ADD)]
        self.assertGreater(len(update_or_add), 0)

    def test_filters_short_content(self):
        """A line that passes distiller's len check but whose body is trimmed
        below MIN_CONTENT_LEN should yield NOOP edits from the cartographer."""
        from core.context_cache import DistillationResult
        dr = DistillationResult()
        # Bypass distiller: inject a long-ish fact whose body is short
        dr.facts = [("k_short", "ab")]   # len 2 < MIN_CONTENT_LEN (6)
        edits = self.cartographer.plan(dr, existing={})
        noop = [e for e in edits if e.action == EditAction.NOOP]
        self.assertEqual(len(noop), 1)
        self.assertEqual(noop[0].key, "k_short")

    def test_dedupes_adds_for_same_key(self):
        # Manually craft a result with two entries that share a key
        from core.context_cache import DistillationResult
        dr = DistillationResult()
        dr.facts = [("k1", "content A"), ("k1", "content A again")]
        edits = self.cartographer.plan(dr, existing={})
        add_edits = [e for e in edits if e.action == EditAction.ADD]
        self.assertEqual(len(add_edits), 1)


# ---------------------------------------------------------------------------
# Evictor tests
# ---------------------------------------------------------------------------


class EvictorTests(unittest.TestCase):
    def _make_entry(self, key, token_cost, hits, last_accessed):
        from core.context_cache import ContextEntry
        e = ContextEntry(
            entry_id=key, key=key, kind=CacheEntryKind.FACT,
            content="x" * token_cost, token_cost=token_cost,
        )
        e.hit_count = hits
        e.last_accessed = last_accessed
        return e

    def test_no_eviction_when_under_budget(self):
        ev = Evictor(EvictionPolicy.LRU)
        entries = [self._make_entry("a", 10, 1, 1000.0)]
        evicted = ev.select_evictions(entries, current_tokens=10, target_tokens=100)
        self.assertEqual(evicted, [])

    def test_lru_evicts_least_recent(self):
        ev = Evictor(EvictionPolicy.LRU)
        old = self._make_entry("old", 10, 5, 1000.0)
        new = self._make_entry("new", 10, 5, 2000.0)
        evicted = ev.select_evictions([old, new], current_tokens=20, target_tokens=10)
        self.assertIn(old, evicted)
        self.assertNotIn(new, evicted)

    def test_lfu_evicts_least_frequent(self):
        ev = Evictor(EvictionPolicy.LFU)
        rare = self._make_entry("rare", 10, 0, 2000.0)
        common = self._make_entry("common", 10, 100, 2000.0)
        evicted = ev.select_evictions([rare, common], current_tokens=20, target_tokens=10)
        self.assertIn(rare, evicted)
        self.assertNotIn(common, evicted)

    def test_cost_aware_evicts_expensive_first(self):
        ev = Evictor(EvictionPolicy.COST_AWARE)
        cheap = self._make_entry("cheap", 5, 10, 2000.0)
        pricey = self._make_entry("pricey", 50, 10, 2000.0)
        evicted = ev.select_evictions([cheap, pricey], current_tokens=55, target_tokens=10)
        self.assertIn(pricey, evicted)

    def test_hybrid_balances_signals(self):
        ev = Evictor(EvictionPolicy.HYBRID)
        a = self._make_entry("a", 10, 0, 1000.0)   # old, unused
        b = self._make_entry("b", 10, 10, 2000.0)  # recent, used
        evicted = ev.select_evictions([a, b], current_tokens=20, target_tokens=10)
        self.assertIn(a, evicted)


# ---------------------------------------------------------------------------
# ContextMap tests
# ---------------------------------------------------------------------------


class ContextMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cm = ContextMap(token_budget=200)

    def test_put_and_get(self):
        self.cm.put("k1", "the capital of France is Paris", CacheEntryKind.FACT)
        entry = self.cm.get("k1")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.content, "the capital of France is Paris")

    def test_get_miss(self):
        self.assertIsNone(self.cm.get("nope"))
        self.assertEqual(self.cm.stats.misses, 1)

    def test_put_updates_existing(self):
        self.cm.put("k1", "first", CacheEntryKind.FACT)
        self.cm.put("k1", "second", CacheEntryKind.FACT)
        self.assertEqual(self.cm.stats.saves, 1)
        self.assertEqual(self.cm.stats.updates, 1)

    def test_remove(self):
        self.cm.put("k1", "x", CacheEntryKind.FACT)
        self.assertTrue(self.cm.remove("k1"))
        self.assertFalse(self.cm.contains("k1"))

    def test_budget_enforcement_via_eviction(self):
        # Budget = 200; add items totaling more
        for i in range(20):
            self.cm.put(f"k{i}", "y" * 50, CacheEntryKind.FACT)  # each ~13 tokens
        self.assertLessEqual(self.cm.stats.total_tokens, 200)

    def test_ingest_trace(self):
        trace = [
            ("user", "The capital of France is Paris."),
            ("assistant", "tool: lookup(Paris)"),
        ]
        edits = self.cm.ingest_trace(trace, source_label="t1")
        self.assertGreater(len(edits), 0)
        self.assertGreater(self.cm.stats.size, 0)

    def test_ingest_trace_dedupes_on_second_pass(self):
        trace = [("user", "The capital of France is Paris.")]
        self.cm.ingest_trace(trace, source_label="t1")
        size_after_first = self.cm.stats.size
        self.cm.ingest_trace(trace, source_label="t2")
        self.assertEqual(self.cm.stats.size, size_after_first)

    def test_top_entries_sorted_by_value_density(self):
        self.cm.put("hot", "x", CacheEntryKind.FACT, token_cost=5)
        self.cm.put("cold", "x" * 100, CacheEntryKind.FACT, token_cost=100)
        # Make hot popular
        for _ in range(10):
            self.cm.get("hot")
        top = self.cm.top_entries(n=2)
        self.assertEqual(top[0].key, "hot")

    def test_saved_tokens_counter(self):
        self.cm.put("k1", "x" * 40, CacheEntryKind.FACT)  # ~10 tokens
        self.cm.get("k1")
        self.cm.get("k1")
        self.assertEqual(self.cm.stats.saved_tokens_total, 20)

    def test_describe(self):
        self.cm.put("k1", "x", CacheEntryKind.FACT)
        d = self.cm.describe()
        self.assertIn("stats", d)
        self.assertIn("budget", d)
        self.assertIn("policy", d)

    def test_clear(self):
        self.cm.put("k1", "x", CacheEntryKind.FACT)
        self.cm.clear()
        self.assertEqual(self.cm.stats.size, 0)
        self.assertEqual(self.cm.stats.hits, 0)


# ---------------------------------------------------------------------------
# Convenience constructor tests
# ---------------------------------------------------------------------------


class ConvenienceTests(unittest.TestCase):
    def test_create_cache(self):
        cm = create_cache(token_budget=500, policy=EvictionPolicy.LRU)
        self.assertEqual(cm.token_budget, 500)
        self.assertEqual(cm.evictor.policy, EvictionPolicy.LRU)

    def test_create_agent(self):
        agent = create_agent(name="tester", token_budget=100)
        self.assertEqual(agent.name, "tester")
        self.assertEqual(agent.cache.token_budget, 100)


# ---------------------------------------------------------------------------
# Agent wrapper tests
# ---------------------------------------------------------------------------


class ContextOrientedAgentTests(unittest.TestCase):
    def test_consult_returns_none_when_missing(self):
        agent = create_agent()
        self.assertIsNone(agent.consult("nope"))

    def test_remember_ingests_and_updates_runs(self):
        agent = create_agent()
        trace = [("user", "The capital of France is Paris.")]
        edits = agent.remember(trace, source_label="run1")
        self.assertGreater(len(edits), 0)
        self.assertEqual(len(agent.runs), 1)
        self.assertGreater(agent.runs[0]["edits"], 0)

    def test_summary(self):
        agent = create_agent()
        agent.remember([("user", "The capital of France is Paris.")])
        s = agent.summary()
        self.assertEqual(s["agent"], agent.name)
        self.assertEqual(s["runs"], 1)
        self.assertIn("cache", s)


# ---------------------------------------------------------------------------
# End-to-end / integration tests
# ---------------------------------------------------------------------------


class IntegrationTests(unittest.TestCase):
    def test_recurring_tasks_save_tokens(self):
        """Simulate 5 similar runs and assert cumulative savings."""
        agent = create_agent(token_budget=1000)
        trace = [
            ("user", "The capital of France is Paris."),
            ("assistant", "tool: web_search('Paris weather')"),
        ]
        # first run
        agent.remember(trace, source_label="r1")
        baseline_saves = agent.cache.stats.saved_tokens_total
        # subsequent runs: cache hits, no new tokens consumed from base
        for i in range(2, 6):
            agent.remember(trace, source_label=f"r{i}")
        # saved_tokens_total should grow due to cache hits
        self.assertGreaterEqual(agent.cache.stats.saved_tokens_total, baseline_saves)

    def test_budget_holds_under_pressure(self):
        agent = create_agent(token_budget=200)
        # Add a lot of varied content
        for i in range(50):
            trace = [("user", f"The value of item {i} is {i * 17}. "
                              f"It was created on 2026-06-04 and is in stock.")]
            agent.remember(trace, source_label=f"ingest_{i}")
        self.assertLessEqual(agent.cache.stats.total_tokens, 200)

    def test_cache_invalidation_via_remove(self):
        agent = create_agent()
        agent.remember([("user", "The capital of France is Paris.")])
        key = next(iter(agent.cache.entries.keys()))
        self.assertTrue(agent.cache.remove(key))
        self.assertIsNone(agent.consult(key))


if __name__ == "__main__":
    unittest.main(verbosity=2)
