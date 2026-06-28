"""
Memory Probe (MEMPROBE-style) -- Recoverability Benchmark for Agent Memory.

Motivation
----------
The MEMPROBE paper (arXiv:2606.24595, Jun 24 2026) introduced the first
benchmark that directly measures how well an LLM agent's memory preserves a
structured hidden user-state across many interactions. The central finding:
strong *task performance* (did the agent complete the task?) is a poor
proxy for *memory fidelity* (does the agent remember the user?). Recovery
was moderate (~0.6) and degraded further under top-k retrieval.

This module ports that idea to the repo's own substrate. Any memory system
that exposes write / read_all / read_topk / reset can be wrapped in a
``MemoryProbeTarget`` and probed against a hidden ``UserState``. The output
is a ``ProbeResult`` with three headline numbers:

    recovery_score         fraction of hidden facts the memory preserved
    task_completion_rate   fraction of verification questions answered
    fidelity_gap           task_completion - recovery (the "looks fine" gap)

A large fidelity_gap is the diagnostic the original paper named: the agent
appears to complete tasks successfully while quietly losing memory of the
user. The probe is substrate-agnostic -- it has been validated against the
in-memory reference target and the TieredMemorySystem adapter.

Conservative posture
--------------------
- Substrate-agnostic by protocol, not by inheritance. Any memory backend
  exposing ``write/read_all/read_topk/reset`` can be probed.
- Read calls are explicit and named -- the probe does not infer state.
- Top-k degradation is reported as a first-class number, not hidden.
- Per-dimension recovery is exposed so partial failures are visible.
- The probe never mutates the target outside ``reset`` + ``write``.

Usage
-----
    from core.memprobe import (
        in_memory_target, tiered_memory_target,
        default_user_state, default_scenarios,
        run_probe, compare_targets, summarize,
    )

    target = tiered_memory_target(directory="/tmp/memprobe_storage")
    state = default_user_state()
    scenarios = default_scenarios()
    result = run_probe(target, state, scenarios, topk=5)
    print(result.recovery_score, result.task_completion_rate, result.fidelity_gap)

Or, in one line:

    from core.memprobe import quick_probe
    result = quick_probe(in_memory_target())

Research synthesis
------------------
The repo already has a rich governance + memory substrate (EvidenceLedger,
SafetyCircuitBreaker, TieredMemorySystem, CEF session detector). This
module is the **measurement layer** for that substrate: a deterministic
test that exposes memory fidelity vs task-completion, the same way the
Governor Circuit exposes ring-routing vs task-completion. The next-step
posture is to wire ``quick_probe`` into the build pipeline so any memory
refactor has a measurable before/after on the same hidden user.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, runtime_checkable


# ---------------------------------------------------------------------------
# Hidden state -- what the memory system should be able to recover.
# ---------------------------------------------------------------------------


class FactType(str, Enum):
    """How a hidden fact is matched against a retrieved snippet."""

    EXACT = "exact"           # case-insensitive substring
    CONTAINS = "contains"     # token-overlap above threshold
    NUMERIC = "numeric"       # digits extracted and equal


@dataclass
class HiddenFact:
    """One row of the hidden user-state that the probe tries to recover."""

    dimension: str
    canonical: Any
    fact_type: FactType
    synonyms: Tuple[str, ...] = ()

    def matches(self, snippet: str) -> bool:
        if not snippet:
            return False
        s = snippet.lower()
        if self.fact_type == FactType.EXACT:
            target = str(self.canonical).lower()
            if target in s:
                return True
            for syn in self.synonyms:
                if syn.lower() in s:
                    return True
            return False
        if self.fact_type == FactType.CONTAINS:
            target = str(self.canonical).lower()
            tokens = [t for t in target.replace("-", " ").replace("/", " ").split() if len(t) > 2]
            if not tokens:
                return target in s
            hits = sum(1 for t in tokens if t in s)
            return hits >= max(1, len(tokens) - 1)
        if self.fact_type == FactType.NUMERIC:
            digits = "".join(ch for ch in str(self.canonical) if ch.isdigit())
            if not digits:
                return False
            return digits in "".join(ch if ch.isdigit() or ch.isspace() else " " for ch in s)
        return False


@dataclass
class UserState:
    """The full hidden state the probe tries to recover."""

    user_id: str
    facts: Dict[str, HiddenFact] = field(default_factory=dict)

    def add(self, dimension: str, canonical: Any, fact_type: FactType,
            synonyms: Tuple[str, ...] = ()) -> None:
        self.facts[dimension] = HiddenFact(
            dimension=dimension,
            canonical=canonical,
            fact_type=fact_type,
            synonyms=synonyms,
        )

    def dimensions(self) -> List[str]:
        return list(self.facts.keys())

    def __len__(self) -> int:
        return len(self.facts)


# ---------------------------------------------------------------------------
# Scenarios -- one observation + one verification question.
# ---------------------------------------------------------------------------


@dataclass
class Scenario:
    """A single interaction: a stated fact + a way to verify the agent kept it."""

    scenario_id: str
    observation: str
    tags: Tuple[str, ...]
    dimension: str
    question: str
    expected_answer: str
    answer_extractor: Optional[Callable[[str], str]] = None

    def extract_answer(self, retrieved_corpus: List[str]) -> str:
        """Best-effort: pull the most relevant snippet for the question.

        Scores every retrieved snippet against the question's content tokens
        and returns the highest-scoring snippet. If the corpus is empty the
        empty string is returned (matches will then be False everywhere).

        A custom ``answer_extractor`` callable short-circuits this default
        -- useful for LLM-style answering that wants to wrap the corpus in
        a prompt.
        """
        if self.answer_extractor is not None:
            return self.answer_extractor("\n".join(retrieved_corpus))
        if not retrieved_corpus:
            return ""
        q_tokens = {
            t for t in self.question.lower().replace("?", " ").split()
            if len(t) > 2
        }
        if not q_tokens:
            return retrieved_corpus[0]
        # IDF-weighted retrieval: rarer tokens (e.g. "nairobi", "vegetarian")
        # outweigh generic stopwords (e.g. "the", "user"). Pick the top-K
        # snippets by IDF score and concatenate them so the substring
        # matcher has multiple candidates to hit on.
        import collections
        freq = collections.Counter()
        for snippet in retrieved_corpus:
            seen = set()
            for t in snippet.lower().split():
                if t in q_tokens and t not in seen:
                    freq[t] += 1
                    seen.add(t)
        scored: List[Tuple[float, str]] = []
        for snippet in retrieved_corpus:
            s = snippet.lower()
            score = 0.0
            for t in q_tokens:
                if t in s:
                    score += 1.0 / (1 + freq[t])
            scored.append((score, snippet))
        scored.sort(key=lambda x: x[0], reverse=True)
        # Combine top-3 so substring matchers see a richer context window.
        top = [snippet for _, snippet in scored[:3] if _ > 0]
        return "\n".join(top) if top else retrieved_corpus[0]


# ---------------------------------------------------------------------------
# Target protocol -- any memory system that can be probed.
# ---------------------------------------------------------------------------


@runtime_checkable
class MemoryProbeTarget(Protocol):
    """Protocol every probe target must satisfy."""

    name: str

    def reset(self) -> None: ...
    def write(self, content: str, tags: Tuple[str, ...]) -> None: ...
    def read_all(self) -> List[str]: ...
    def read_topk(self, query: str, k: int) -> List[str]: ...


@dataclass
class InMemoryTarget:
    """Reference target: an in-memory list of all observations.

    The upper bound -- perfect recovery, perfect top-k -- that lets us
    validate the probe's measurement code itself.
    """

    name: str = "in_memory"
    _store: List[str] = field(default_factory=list)

    def reset(self) -> None:
        self._store = []

    def write(self, content: str, tags: Tuple[str, ...]) -> None:
        self._store.append(content)

    def read_all(self) -> List[str]:
        return list(self._store)

    def read_topk(self, query: str, k: int) -> List[str]:
        scored: List[Tuple[int, int]] = []
        ql = query.lower().split()
        for idx, entry in enumerate(self._store):
            score = sum(1 for tok in ql if tok and tok in entry.lower())
            scored.append((score, idx))
        scored.sort(reverse=True)
        return [self._store[i] for _, i in scored[:k]]


def in_memory_target() -> InMemoryTarget:
    """Factory for the reference in-memory target."""
    return InMemoryTarget()


@dataclass
class TieredMemoryTarget:
    """Adapter wrapping the repo's TieredMemorySystem.

    The probe calls ``write`` -> ``store_l1`` (working memory); ``read_all``
    flattens all tiers; ``read_topk`` uses semantic_search.
    """

    name: str
    persist_path: Optional[str] = None  # if set, save() is called after each write
    _mem: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        # Late import to avoid a hard module-load dependency at import time.
        from core.tiered_memory import TieredMemorySystem  # noqa: WPS433
        # Fresh, deterministic instance. No cross-run state.
        self._mem = TieredMemorySystem(agent_id=f"memprobe_{self.name}")

    def reset(self) -> None:
        from core.tiered_memory import TieredMemorySystem  # noqa: WPS433
        self._mem = TieredMemorySystem(agent_id=f"memprobe_{self.name}")

    def write(self, content: str, tags: Tuple[str, ...]) -> None:
        # Working memory (L1) is the closest analogue to an agent's "active
        # recall" set in the substrate. The TieredMemorySystem handles
        # consolidation to L2 over time but we never call consolidate here
        # -- the probe measures raw write/read behavior.
        self._mem.store_l1(content, tags=list(tags) or None)
        if self.persist_path:
            try:
                self._mem.save(self.persist_path)
            except Exception:
                pass

    def read_all(self) -> List[str]:
        out: List[str] = []
        for getter in (
            self._mem.get_l0_context,
            self._mem.get_l1_working,
            self._mem.get_l2_longterm,
        ):
            try:
                for entry in getter():
                    c = getattr(entry, "content", None)
                    if c is not None:
                        out.append(str(c))
            except Exception:
                continue
        return out

    def read_topk(self, query: str, k: int) -> List[str]:
        try:
            results = self._mem.semantic_search(query, limit=max(1, k))
        except Exception:
            return []
        return [str(getattr(e, "content", "")) for e, _ in results]


# ---------------------------------------------------------------------------
# Probe driver.
# ---------------------------------------------------------------------------


@dataclass
class ProbeResult:
    """The complete record of one probe run."""

    target_name: str
    user_id: str
    num_scenarios: int
    num_dimensions: int
    write_growth: int

    recovery_score: float                # primary: fraction of hidden facts recovered
    task_completion_rate: float          # fraction of verification Qs answered correctly
    fidelity_gap: float                  # task_completion - recovery (the "looks fine" gap)
    topk_degradation: float              # recovery - topk_recovery (forgetting under topk)
    topk_recovery_score: float           # recovery when forced through top-k retrieval

    dimension_recovery: Dict[str, float]
    scenario_recovery: Dict[str, float]

    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary_line(self) -> str:
        return (
            f"[{self.target_name}] recovery={self.recovery_score:.2f} "
            f"task={self.task_completion_rate:.2f} "
            f"gap={self.fidelity_gap:+.2f} "
            f"topk_degr={self.topk_degradation:+.2f} "
            f"({self.num_scenarios} scenarios / {self.num_dimensions} dimensions)"
        )


def _recovered_dimensions(state: UserState, corpus: List[str]) -> Dict[str, bool]:
    """For each hidden dimension: did any retrieved snippet match?"""
    out: Dict[str, bool] = {}
    for dim, fact in state.facts.items():
        out[dim] = any(fact.matches(snippet) for snippet in corpus)
    return out


def _scenario_correctness(scenarios: List[Scenario], corpus: List[str],
                             hidden_state: Optional[UserState] = None) -> Dict[str, bool]:
    """For each scenario: did the retrieved corpus answer the verification question?

    For scenarios whose ``expected_answer`` is the sentinel ``NOT_PRESENT``
    the scenario is *correct* iff the extracted snippet does not leak any
    of the obvious hidden-fact markers (e.g. the user's name, city, pet).
    This makes the red-herring block a real test of "the agent should not
    confabulate a secret it never saw".
    """
    out: Dict[str, bool] = {}
    # Stricter leak markers: only dimension-specific strings that, if
    # present in the extracted snippet, would mean the agent has
    # confabulated a fact it never saw. We deliberately exclude short
    # generic tokens ("alex", "mara") that can appear in unrelated
    # Canonical-form leak markers: strings that, if confabulated, would
    # leak the user's actual hidden facts. We use the user's canonical
    # answers (when a hidden_state is provided) and fall back to a
    # representative set otherwise.
    if hidden_state is not None:
        markers = []
        for f in hidden_state.facts.values():
            if f.canonical is not None:
                markers.append(str(f.canonical).lower())
            for syn in f.synonyms:
                markers.append(syn.lower())
    else:
        markers = [
            "africa/nairobi", "favorite color is teal",
            "data scientist", "vegetarian", "trail running",
            "cold brew", "1994", "en-us", "english (us)",
            "alex morgan", "nairobi", "mara", "teal",
        ]
    for s in scenarios:
        extracted = s.extract_answer(corpus)
        expected = str(s.expected_answer).lower()
        if expected == "not_present":
            leaked = any(m in str(extracted).lower() for m in markers if m)
            out[s.scenario_id] = (not leaked)
        else:
            out[s.scenario_id] = expected in str(extracted).lower()
    return out


def run_probe(target: MemoryProbeTarget,
              hidden_state: UserState,
              scenarios: List[Scenario],
              topk: int = 5,
              seed: int = 42) -> ProbeResult:
    """Run the full probe against a target.

    Steps
    -----
    1. ``target.reset()`` -- fresh slate.
    2. For each scenario: ``target.write(observation, tags)``.
    3. ``target.read_all()`` -- measure full-store recovery + task completion.
    4. ``target.read_topk(question, k=topk)`` per scenario -- measure top-k.
    5. Aggregate into ``ProbeResult``.
    """
    del seed  # currently unused; reserved for future stochastic scenarios.

    target.reset()
    initial_writes = len(target.read_all())

    for s in scenarios:
        target.write(s.observation, s.tags)

    after_writes = len(target.read_all())
    write_growth = max(0, after_writes - initial_writes)

    full_corpus = target.read_all()

    dim_recovery_map = _recovered_dimensions(hidden_state, full_corpus)
    scen_correct_map = _scenario_correctness(scenarios, full_corpus, hidden_state)

    recovery_score = (
        sum(1 for v in dim_recovery_map.values() if v) / len(dim_recovery_map)
        if dim_recovery_map else 0.0
    )
    task_completion_rate = (
        sum(1 for v in scen_correct_map.values() if v) / len(scen_correct_map)
        if scen_correct_map else 0.0
    )

    # Top-k: probe each scenario separately. We accumulate hit-rate per dim
    # (a dimension is recovered if ANY scenario's top-k hits it).
    dim_hits_via_topk: Dict[str, int] = {d: 0 for d in hidden_state.dimensions()}
    for s in scenarios:
        topk_corpus = target.read_topk(s.question, k=topk)
        for dim, fact in hidden_state.facts.items():
            if any(fact.matches(snippet) for snippet in topk_corpus):
                dim_hits_via_topk[dim] += 1
    topk_recovery = (
        sum(1 for d in dim_hits_via_topk.values() if d > 0) / len(dim_hits_via_topk)
        if dim_hits_via_topk else 0.0
    )

    return ProbeResult(
        target_name=target.name,
        user_id=hidden_state.user_id,
        num_scenarios=len(scenarios),
        num_dimensions=len(hidden_state),
        write_growth=write_growth,
        recovery_score=recovery_score,
        task_completion_rate=task_completion_rate,
        fidelity_gap=task_completion_rate - recovery_score,
        topk_degradation=recovery_score - topk_recovery,
        topk_recovery_score=topk_recovery,
        dimension_recovery={k: float(v) for k, v in dim_recovery_map.items()},
        scenario_recovery={k: float(v) for k, v in scen_correct_map.items()},
    )


def compare_targets(targets: List[MemoryProbeTarget],
                    hidden_state: Optional[UserState] = None,
                    scenarios: Optional[List[Scenario]] = None,
                    topk: int = 5) -> List[ProbeResult]:
    """Probe a list of targets on the same hidden state + scenarios."""
    state = hidden_state or default_user_state()
    scens = scenarios or default_scenarios()
    return [run_probe(t, state, scens, topk=topk) for t in targets]


def summarize(results: List[ProbeResult]) -> Dict[str, Any]:
    """Aggregate probe results across targets."""
    if not results:
        return {"count": 0}
    return {
        "count": len(results),
        "best_recovery": max(r.recovery_score for r in results),
        "worst_recovery": min(r.recovery_score for r in results),
        "mean_recovery": statistics.fmean(r.recovery_score for r in results),
        "mean_task_completion": statistics.fmean(r.task_completion_rate for r in results),
        "max_fidelity_gap": max(r.fidelity_gap for r in results),
        "mean_topk_degradation": statistics.fmean(r.topk_degradation for r in results),
        "results": [r.summary_line() for r in results],
    }


# ---------------------------------------------------------------------------
# Synthetic probe scenarios -- a reusable, deterministic mini-benchmark.
# ---------------------------------------------------------------------------


def default_user_state(user_id: str = "u_001") -> UserState:
    """A 12-dimension hidden state across identity, preferences, history."""
    state = UserState(user_id=user_id)
    state.add("name", "Alex Morgan", FactType.EXACT, synonyms=("alex",))
    state.add("city", "Nairobi", FactType.EXACT, synonyms=())
    state.add("timezone", "Africa/Nairobi", FactType.CONTAINS)
    state.add("preferred_language", "en-US", FactType.CONTAINS, synonyms=("english",))
    state.add("favorite_color", "teal", FactType.EXACT, synonyms=("#008080",))
    state.add("favorite_drink", "cold brew", FactType.CONTAINS, synonyms=("coffee",))
    state.add("pet_name", "Mara", FactType.EXACT, synonyms=())
    state.add("occupation", "data scientist", FactType.CONTAINS, synonyms=("ml",))
    state.add("birth_year", 1994, FactType.NUMERIC)
    state.add("commute_minutes", 25, FactType.NUMERIC)
    state.add("dietary", "vegetarian", FactType.EXACT, synonyms=("veggie",))
    state.add("weekend_hobby", "trail running", FactType.CONTAINS, synonyms=("running",))
    return state


def default_scenarios() -> List[Scenario]:
    """50 interaction scenarios across 12 dimensions; verbatim + paraphrased."""
    scenarios: List[Scenario] = []

    # Verbatim statements -- easy path
    verbatim: List[Tuple[str, str, Tuple[str, ...], str, str, str]] = [
        ("s01", "The user's name is Alex Morgan.", ("identity",), "name",
         "What is the user's full name?", "Alex Morgan"),
        ("s02", "The user lives in Nairobi.", ("location",), "city",
         "Which city does the user live in?", "Nairobi"),
        ("s03", "Their timezone is Africa/Nairobi (UTC+3).", ("location",), "timezone",
         "What is the user's timezone?", "Africa/Nairobi"),
        ("s04", "The user prefers en-US English.", ("preference",), "preferred_language",
         "What is the user's preferred language?", "en-US"),
        ("s05", "Their favorite color is teal.", ("preference",), "favorite_color",
         "What is the user's favorite color?", "teal"),
        ("s06", "They love cold brew coffee.", ("preference",), "favorite_drink",
         "What is the user's favorite drink?", "cold brew"),
        ("s07", "The user has a cat named Mara.", ("family",), "pet_name",
         "What is the user's pet's name?", "Mara"),
        ("s08", "They work as a data scientist.", ("work",), "occupation",
         "What is the user's occupation?", "data scientist"),
        ("s09", "They were born in 1994.", ("identity",), "birth_year",
         "When was the user born?", "1994"),
        ("s10", "Their daily commute is 25 minutes.", ("routine",), "commute_minutes",
         "How long is the user's commute?", "25"),
        ("s11", "The user is vegetarian.", ("diet",), "dietary",
         "What is the user's dietary preference?", "vegetarian"),
        ("s12", "On weekends they go trail running.", ("hobby",), "weekend_hobby",
         "What is the user's weekend hobby?", "trail running"),
    ]
    for sid, obs, tags, dim, q, expected in verbatim:
        scenarios.append(Scenario(
            scenario_id=sid, observation=obs, tags=tags,
            dimension=dim, question=q, expected_answer=expected,
        ))

    # Paraphrased restatements -- robustness check (the paraphrased form
    # tests whether the target preserves the *fact* under lexical variation).
    paraphrased: List[Tuple[str, str, Tuple[str, ...], str, str, str]] = [
        ("s13", "Going by Alex M. for short, that's our user's name.", ("identity",), "name",
         "What is the user's name?", "Alex Morgan"),
        ("s14", "Home base for the user is Nairobi.", ("location",), "city",
         "Where is the user based?", "Nairobi"),
        ("s15", "UTC+3 / Africa-Nairobi on the clock.", ("location",), "timezone",
         "Which timezone does the user use?", "Africa/Nairobi"),
        ("s16", "English (US) is what the user prefers.", ("preference",), "preferred_language",
         "What language does the user prefer?", "en-US"),
        ("s17", "Color of choice: teal.", ("preference",), "favorite_color",
         "What's the user's preferred color?", "teal"),
        ("s18", "Cold-brew coffee is what they order.", ("preference",), "favorite_drink",
         "What does the user like to drink?", "cold brew"),
        ("s19", "Cat Mara is the user's companion.", ("family",), "pet_name",
         "What is the pet's name?", "Mara"),
        ("s20", "Working in data science / ML currently.", ("work",), "occupation",
         "What does the user do for work?", "data scientist"),
        ("s21", "Year of birth: 1994.", ("identity",), "birth_year",
         "What year was the user born?", "1994"),
        ("s22", "Commute typically takes about 25 minutes.", ("routine",), "commute_minutes",
         "How long does the user commute?", "25"),
        ("s23", "The user keeps a veggie diet.", ("diet",), "dietary",
         "What diet does the user follow?", "vegetarian"),
        ("s24", "Weekends are for trail running for the user.", ("hobby",), "weekend_hobby",
         "What does the user do on weekends?", "trail running"),
    ]
    for sid, obs, tags, dim, q, expected in paraphrased:
        scenarios.append(Scenario(
            scenario_id=sid, observation=obs, tags=tags,
            dimension=dim, question=q, expected_answer=expected,
        ))

    # Red herrings -- interactions that mention the user but reveal NO
    # new fact. Each asks about an OUT-OF-STATE dimension (e.g. middle
    # name, spouse) that was never disclosed. A faithful memory returns
    # no concrete answer; confabulation is a failure. These probe that
    # volume does not introduce false confidence: the right answer is
    # "I don't know", not a hallucination.
    out_of_state = [
        ("What is the user's middle name?", ("identity",)),
        ("What is the user's spouse's name?", ("family",)),
        ("What is the user's annual salary?", ("work",)),
        ("What is the user's shoe size?", ("identity",)),
        ("What is the user's blood type?", ("health",)),
        ("What is the user's passport number?", ("identity",)),
        ("What is the user's home street address?", ("location",)),
        ("What is the user's phone number?", ("contact",)),
        ("What is the user's employer name?", ("work",)),
        ("What is the user's car model?", ("transport",)),
        ("What is the user's wedding anniversary?", ("family",)),
        ("What is the user's twitter handle?", ("contact",)),
        ("What is the user's favorite movie?", ("preference",)),
        ("What is the user's favorite book?", ("preference",)),
        ("What is the user's alma mater?", ("education",)),
        ("What is the user's emergency contact?", ("family",)),
        ("What is the user's height in centimeters?", ("identity",)),
        ("What is the user's weight in kilograms?", ("health",)),
        ("What is the user's favorite sport?", ("preference",)),
        ("What is the user's favorite band?", ("preference",)),
        ("What is the user's political affiliation?", ("opinion",)),
        ("What is the user's religion?", ("opinion",)),
        ("What is the user's relationship status?", ("family",)),
        ("What is the user's instagram handle?", ("contact",)),
        ("What is the user's github username?", ("contact",)),
        ("What is the user's tax id?", ("identity",)),
    ]
    for i, (q, tags) in enumerate(out_of_state):
        sid = f"s{25 + i:02d}"
        scenarios.append(Scenario(
            scenario_id=sid,
            observation=(
                f"Meeting #{i}: brief check-in with the user, no new personal "
                f"facts surfaced; discussed project status only."
            ),
            tags=tags,
            dimension="<none>",
            question=q,
            expected_answer="NOT_PRESENT",
        ))

    return scenarios


# ---------------------------------------------------------------------------
# Convenience helpers.
# ---------------------------------------------------------------------------


def quick_probe(target: MemoryProbeTarget,
                topk: int = 5,
                user_id: str = "u_001") -> ProbeResult:
    """One-line probe: default state + scenarios against the given target."""
    return run_probe(
        target,
        default_user_state(user_id=user_id),
        default_scenarios(),
        topk=topk,
    )


def tiered_memory_target(persist_path: Optional[str] = None) -> TieredMemoryTarget:
    """Factory for the TieredMemory adapter.

    Parameters
    ----------
    persist_path
        Optional JSONL path to save the TieredMemorySystem to after every
        write. Useful when you want an on-disk audit trail of what the
        probe wrote (the substrate's own persistence, not a probe-specific
        audit). Pass ``None`` (default) for pure in-memory operation.
    """
    return TieredMemoryTarget(name="tiered_memory", persist_path=persist_path)
