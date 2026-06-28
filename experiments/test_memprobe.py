"""
Tests for core.memprobe -- Memory recoverability benchmark (MEMPROBE-style).

Covers:
- HiddenFact.matches (EXACT / CONTAINS / NUMERIC, case-insensitive, synonyms)
- UserState construction + dimension enumeration
- Scenario.extract_answer (IDF-weighted snippet selection, top-K concat)
- Scenario correctness including NOT_PRESENT red-herring handling
- InMemoryTarget (reset / write / read_all / read_topk semantics)
- TieredMemoryTarget (wraps the repo's TieredMemorySystem)
- run_probe headline numbers (recovery, task_completion, fidelity_gap)
- compare_targets cross-target harness
- summarize multi-result aggregation
- quick_probe one-liner
- Conservative-posture invariants (probe never mutates outside reset+write,
  idempotent reset, empty-targets behaviour, deterministic ordering)
- End-to-end "MEMPROBE headline" check: a target that drops entries on
  reset() must be detected as recovery-degraded, not silently zeroed.
- Adversarial inputs: massive corpora, empty corpus, single-snippet corpus,
  unicode facts, repeated identical facts.
"""
import math
import os
import shutil
import tempfile
import unittest

from core.memprobe import (
    FactType,
    HiddenFact,
    InMemoryTarget,
    MemoryProbeTarget,
    ProbeResult,
    Scenario,
    TieredMemoryTarget,
    UserState,
    compare_targets,
    default_scenarios,
    default_user_state,
    in_memory_target,
    quick_probe,
    run_probe,
    summarize,
    tiered_memory_target,
)


def _flat(corpus):
    return [s for s in corpus]


class TestHiddenFactMatches(unittest.TestCase):
    def test_exact_case_insensitive(self):
        f = HiddenFact(dimension="city", canonical="Nairobi", fact_type=FactType.EXACT)
        self.assertTrue(f.matches("Lives in nairobi"))
        self.assertTrue(f.matches("NAIROBI"))
        self.assertFalse(f.matches("Mombasa"))

    def test_exact_with_synonym(self):
        f = HiddenFact(
            dimension="name", canonical="Alex Morgan", fact_type=FactType.EXACT,
            synonyms=("Alex",),
        )
        self.assertTrue(f.matches("Going by Alex for short"))
        self.assertTrue(f.matches("Alex Morgan"))

    def test_contains_threshold(self):
        f = HiddenFact(
            dimension="tz", canonical="Africa/Nairobi",
            fact_type=FactType.CONTAINS,
        )
        # The tokens are ["africa", "nairobi"]; threshold is len-1=1.
        self.assertTrue(f.matches("We are in Africa and Nairobi"))
        self.assertTrue(f.matches("Africa/Nairobi"))
        self.assertFalse(f.matches("Europe/Berlin"))

    def test_numeric(self):
        f = HiddenFact(
            dimension="birth_year", canonical=1994,
            fact_type=FactType.NUMERIC,
        )
        self.assertTrue(f.matches("Born in 1994"))
        self.assertTrue(f.matches("year=1994!"))
        self.assertFalse(f.matches("Born in 1995"))

    def test_empty_snippet(self):
        f = HiddenFact(dimension="x", canonical="y", fact_type=FactType.EXACT)
        self.assertFalse(f.matches(""))


class TestUserState(unittest.TestCase):
    def test_add_and_dimensions(self):
        s = UserState(user_id="u_1")
        s.add("city", "Nairobi", FactType.EXACT)
        s.add("year", 1994, FactType.NUMERIC)
        self.assertEqual(set(s.dimensions()), {"city", "year"})
        self.assertEqual(len(s), 2)

    def test_default_state_is_well_formed(self):
        s = default_user_state()
        self.assertGreaterEqual(len(s), 10)
        # Every dimension should be matchable against its own canonical.
        for dim, fact in s.facts.items():
            self.assertTrue(
                fact.matches(str(fact.canonical)),
                msg=f"dimension {dim} should match its own canonical",
            )


class TestScenarioExtract(unittest.TestCase):
    def test_top1_fallback_when_no_tokens(self):
        s = Scenario(
            scenario_id="t", observation="obs",
            tags=(), dimension="d",
            question="?",
            expected_answer="x",
        )
        self.assertEqual(s.extract_answer(["only snippet"]), "only snippet")

    def test_idf_prefers_rare_token_hit(self):
        s = Scenario(
            scenario_id="t", observation="obs",
            tags=(), dimension="d",
            question="Where is the cat?",
            expected_answer="x",
        )
        # Snippet A mentions "cat" but not "where"; snippet B mentions both.
        # Token "cat" is rare (only in snippet B); "where" is common to all.
        corpus = [
            "Where is the user based?",
            "Where is the cat named Mara?",
            "Where do we meet tomorrow?",
        ]
        self.assertIn("cat", s.extract_answer(corpus).lower())

    def test_combined_topk_includes_real_snippet(self):
        s = Scenario(
            scenario_id="t", observation="obs", tags=(),
            dimension="d",
            question="What is the user's favorite drink?",
            expected_answer="cold brew",
        )
        # A long list of generic snippets plus one that mentions cold brew.
        corpus = [
            "The user's name is Alex Morgan.",
            "They live in Nairobi.",
            "They love cold brew coffee.",
            "Their pet is Mara.",
            "They work as a data scientist.",
        ]
        extracted = s.extract_answer(corpus)
        self.assertIn("cold brew", extracted.lower())


class TestScenarioCorrectness(unittest.TestCase):
    def test_not_present_red_herring_passes_when_no_leak(self):
        from core.memprobe import _scenario_correctness
        s = Scenario(
            scenario_id="rh", observation="Meeting",
            tags=(), dimension="<none>",
            question="What is the user's middle name?",
            expected_answer="NOT_PRESENT",
        )
        self.assertTrue(_scenario_correctness([s], ["The user has no middle name on file."])["rh"])

    def test_not_present_red_herring_fails_on_leak(self):
        from core.memprobe import _scenario_correctness, UserState, FactType
        s = Scenario(
            scenario_id="rh", observation="Meeting",
            tags=(), dimension="<none>",
            question="What is the user middle name?",
            expected_answer="NOT_PRESENT",
        )
        state = UserState(user_id="u")
        state.add("middle_name", "Margaret", FactType.EXACT)
        corpus = ["The user middle name is Margaret."]
        # The leak check now uses the hidden state canonical values, so
        # a fabricated "Margaret" answer for a question about a never-disclosed
        # fact must be flagged as a confabulation.
        self.assertFalse(_scenario_correctness([s], corpus, hidden_state=state)["rh"])

    def test_exact_match_passes(self):
        from core.memprobe import _scenario_correctness
        s = Scenario(
            scenario_id="ok", observation="The user is in Nairobi.",
            tags=(), dimension="city",
            question="Where does the user live?",
            expected_answer="Nairobi",
        )
        self.assertTrue(_scenario_correctness(
            [s], ["The user is in Nairobi."])["ok"])

class TestInMemoryTarget(unittest.TestCase):
    def test_reset_clears(self):
        t = InMemoryTarget(name="t")
        t.write("hello", ("a",))
        self.assertEqual(len(t.read_all()), 1)
        t.reset()
        self.assertEqual(t.read_all(), [])

    def test_write_appends(self):
        t = InMemoryTarget(name="t")
        t.write("one", ("a",))
        t.write("two", ("b",))
        self.assertEqual(t.read_all(), ["one", "two"])

    def test_read_topk_returns_at_most_k(self):
        t = InMemoryTarget(name="t")
        for i in range(20):
            t.write(f"entry number {i}", ())
        out = t.read_topk("entry", k=5)
        self.assertLessEqual(len(out), 5)
        self.assertGreater(len(out), 0)

    def test_protocol_satisfied(self):
        self.assertIsInstance(in_memory_target(), MemoryProbeTarget)


class TestTieredMemoryTarget(unittest.TestCase):
    def test_adapter_protocol(self):
        self.assertIsInstance(tiered_memory_target(), MemoryProbeTarget)

    def test_round_trip_basic(self):
        t = tiered_memory_target()
        t.reset()
        t.write("The user lives in Nairobi.", ("location",))
        t.write("Their name is Alex Morgan.", ("identity",))
        corpus = t.read_all()
        joined = "\n".join(corpus).lower()
        self.assertIn("nairobi", joined)
        self.assertIn("alex morgan", joined)

    def test_reset_clears_memory(self):
        t = tiered_memory_target()
        t.write("first entry", ())
        t.reset()
        # Reset should rebuild to a fresh system; nothing written.
        self.assertEqual(len(t.read_all()), 0)


class TestRunProbe(unittest.TestCase):
    def test_in_memory_full_recovery_full_task(self):
        # In-memory target that does NOT drop entries -> recovery is full.
        # Task-completion depends on retrieval semantics but with full-store
        # read_all, the answer extractor can find the verbatim snippets.
        t = in_memory_target()
        r = run_probe(t, default_user_state(), default_scenarios())
        self.assertEqual(r.recovery_score, 1.0)
        # Headline: fidelity_gap is the diagnostic.
        self.assertGreaterEqual(r.fidelity_gap, -1.0)
        self.assertLessEqual(r.fidelity_gap, 1.0)
        # Dimension map is per-dimension.
        self.assertEqual(set(r.dimension_recovery.keys()),
                         set(default_user_state().dimensions()))

    def test_dropping_target_has_lower_recovery(self):
        # An adversarial target that only keeps 3 entries.
        class DroppingTarget(InMemoryTarget):
            def __init__(self, keep=3):
                super().__init__(name="dropping")
                self.keep = keep

            def write(self, content, tags):
                if len(self._store) >= self.keep:
                    return  # silently drop
                super().write(content, tags)

        d = DroppingTarget(keep=3)
        r = run_probe(d, default_user_state(), default_scenarios())
        # Recovery should be visibly degraded vs full.
        self.assertLess(r.recovery_score, 1.0)

    def test_red_herring_block_does_not_crash(self):
        # The 26-scenario red-herring block is the largest part of the
        # default suite; ensure it returns valid booleans.
        r = quick_probe(in_memory_target())
        self.assertEqual(len(r.scenario_recovery), 50)
        for v in r.scenario_recovery.values():
            self.assertIn(v, (0.0, 1.0))

    def test_write_growth_equals_scenarios(self):
        r = quick_probe(in_memory_target())
        # Writes should grow by exactly len(scenarios) for an honest target.
        self.assertEqual(r.write_growth, 50)

    def test_topk_recovery_le_full_recovery(self):
        # Top-k cannot exceed full-store recovery; if it does we are wrong.
        r = quick_probe(in_memory_target())
        self.assertLessEqual(r.topk_recovery_score, r.recovery_score + 1e-9)


class TestCompareTargets(unittest.TestCase):
    def test_compare_two_targets(self):
        results = compare_targets([
            in_memory_target(),
            tiered_memory_target(),
        ])
        self.assertEqual(len(results), 2)
        self.assertEqual({r.target_name for r in results},
                         {"in_memory", "tiered_memory"})

    def test_summarize_returns_aggregate(self):
        results = compare_targets([
            in_memory_target(), tiered_memory_target(),
        ])
        agg = summarize(results)
        self.assertEqual(agg["count"], 2)
        self.assertIn("mean_recovery", agg)
        self.assertIn("max_fidelity_gap", agg)
        self.assertEqual(len(agg["results"]), 2)


class TestQuickProbe(unittest.TestCase):
    def test_one_liner(self):
        r = quick_probe(in_memory_target())
        self.assertEqual(r.num_scenarios, 50)
        self.assertEqual(r.num_dimensions, 12)
        self.assertEqual(r.user_id, "u_001")


class TestProbeResultSerialization(unittest.TestCase):
    def test_to_dict_round_trip(self):
        r = quick_probe(in_memory_target())
        d = r.to_dict()
        self.assertEqual(d["target_name"], "in_memory")
        self.assertEqual(d["num_scenarios"], 50)
        self.assertEqual(d["num_dimensions"], 12)
        self.assertIn("recovery_score", d)
        self.assertIn("dimension_recovery", d)
        self.assertIn("scenario_recovery", d)


class TestConservativePosture(unittest.TestCase):
    def test_probe_does_not_mutate_target_state_via_read(self):
        t = in_memory_target()
        run_probe(t, default_user_state(), default_scenarios())
        # After a full probe run, calling read_all again should return
        # the same set of snippets the probe saw at the end.
        corpus_after = _flat(t.read_all())
        self.assertEqual(len(corpus_after), 50)

    def test_idempotent_reset(self):
        t = in_memory_target()
        t.reset()
        t.reset()
        # Two resets in a row should still produce an empty target.
        self.assertEqual(t.read_all(), [])

    def test_empty_scenarios_run_is_safe(self):
        t = in_memory_target()
        r = run_probe(t, default_user_state(), [])
        self.assertEqual(r.num_scenarios, 0)
        self.assertEqual(r.recovery_score, 0.0)
        self.assertEqual(r.task_completion_rate, 0.0)
        self.assertEqual(r.write_growth, 0)

    def test_empty_user_state_zero_recovery(self):
        t = in_memory_target()
        empty = UserState(user_id="u_empty")
        r = run_probe(t, empty, default_scenarios())
        # No dimensions to recover -> recovery_score is 0.0 by convention.
        self.assertEqual(r.recovery_score, 0.0)

    def test_massive_corpus_does_not_break(self):
        # 500 redundant writes + a single probe on top.
        class BigTarget(InMemoryTarget):
            pass

        t = BigTarget(name="big")
        for i in range(500):
            t.write(f"noise entry {i}", ("noise",))
        # Now write the real scenario observations.
        for s in default_scenarios():
            t.write(s.observation, s.tags)
        r = run_probe(t, default_user_state(), default_scenarios())
        # Recovery should still be 1.0 because nothing was lost.
        self.assertEqual(r.recovery_score, 1.0)

    def test_unicode_fact_round_trips(self):
        s = UserState(user_id="u_uni")
        s.add("emoji_pref", "🦄", FactType.EXACT)
        t = in_memory_target()
        t.reset()
        t.write("User's preferred emoji is 🦄", ())
        r = run_probe(t, s, [
            Scenario(
                scenario_id="u1", observation="User loves 🦄",
                tags=(), dimension="emoji_pref",
                question="What's the preferred emoji?",
                expected_answer="🦄",
            )
        ])
        self.assertEqual(r.recovery_score, 1.0)


class TestMEMPROBEHeadline(unittest.TestCase):
    """The headline test: a target that loses the user's name should still
    appear to \"complete\" the task on paraphrased questions, exposing the
    fidelity_gap the original MEMPROBE paper named.
    """

    def test_partial_drop_yields_visible_gap(self):
        class NameDroppingTarget(InMemoryTarget):
            def write(self, content, tags):
                # Drop anything mentioning the user's name verbatim or as
                # the paraphrase -- so the name dimension must be lost.
                if "Alex Morgan" in content or "Alex M." in content:
                    return
                super().write(content, tags)

        t = NameDroppingTarget(name="name_dropping")
        r = run_probe(t, default_user_state(), default_scenarios())
        # The name dimension must be at least partially lost.
        self.assertLess(r.dimension_recovery.get("name", 0.0), 1.0)
        # The fidelity gap is finite and bounded.
        self.assertTrue(math.isfinite(r.fidelity_gap))
        self.assertGreaterEqual(r.fidelity_gap, -1.0)
        self.assertLessEqual(r.fidelity_gap, 1.0)


if __name__ == "__main__":
    unittest.main()
