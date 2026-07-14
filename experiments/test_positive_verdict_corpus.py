"""Tests for the positive verdict corpus (2026-07-14 build).

Covers:
- CorpusEntry / SkillTemplate data-shape invariants
- chain_fingerprint determinism (same chain -> same digest, different chain -> different)
- PositiveVerdictCorpus.record (allow-only, idempotent on duplicate)
- chain_seen + filter by gate_version / capability_set_id
- by_capability_set / by_gate / query with shape_match
- verify_entry (live re-evaluation matches frozen verdict)
- extract_skills: groups entries by shape; use_count increments
- find_skill: pattern-match future chain against extracted skills
- attach_trip_engine: handoff works, detach clears
- to_json / from_json round-trip
- corpus_identity_digest: order-independent
- Negative case: BLOCK verdicts are rejected
"""
from __future__ import annotations

import pytest

from core.positive_verdict_corpus import (
    CorpusEntry,
    PositiveVerdictCorpus,
    SkillTemplate,
    chain_fingerprint,
    _compute_corpus_digest,
    _corpus_identity_digest,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _chain(*verbs):
    return [{"verb": v, "args": {}} for v in verbs]


def _entry(
    chain,
    action="allow",
    gate_version="v1.0",
    capability_set_id="default",
    verdict_digest=None,
    reason="routine",
    provenance="test",
):
    return CorpusEntry(
        chain=chain,
        verdict_action=action,
        verdict_digest=verdict_digest or f"vd-{chain_fingerprint(chain)[:12]}",
        gate_version=gate_version,
        capability_set_id=capability_set_id,
        reason=reason,
        provenance=provenance,
    )


# ---------------------------------------------------------------------------
# chain_fingerprint determinism
# ---------------------------------------------------------------------------


class TestChainFingerprint:
    def test_same_chain_same_digest(self):
        a = _chain("read_env", "http_post_external")
        b = _chain("read_env", "http_post_external")
        assert chain_fingerprint(a) == chain_fingerprint(b)

    def test_different_chain_different_digest(self):
        a = _chain("read_env", "http_post_external")
        b = _chain("read_env", "http_post_internal")
        assert chain_fingerprint(a) != chain_fingerprint(b)

    def test_reversed_chain_different_digest(self):
        a = _chain("read_env", "http_post_external")
        b = _chain("http_post_external", "read_env")
        assert chain_fingerprint(a) != chain_fingerprint(b)

    def test_extra_args_does_not_break(self):
        a = _chain("read_env")
        b = _chain("read_env")
        assert chain_fingerprint(a) == chain_fingerprint(b)

    def test_returns_64_char_hex(self):
        fp = chain_fingerprint(_chain("read_env"))
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)


# ---------------------------------------------------------------------------
# CorpusEntry invariants
# ---------------------------------------------------------------------------


class TestCorpusEntry:
    def test_rejects_block_action(self):
        with pytest.raises(AssertionError):
            CorpusEntry(
                chain=_chain("read_env"),
                verdict_action="block",
                verdict_digest="x",
                gate_version="v1",
                capability_set_id="c",
            )

    def test_rejects_block_and_escalate(self):
        with pytest.raises(AssertionError):
            CorpusEntry(
                chain=_chain("read_env"),
                verdict_action="block_and_escalate",
                verdict_digest="x",
                gate_version="v1",
                capability_set_id="c",
            )

    def test_corpus_digest_is_deterministic(self):
        e1 = _entry(_chain("read_env", "http_post_internal"), gate_version="v1")
        e2 = _entry(_chain("read_env", "http_post_internal"), gate_version="v1")
        assert e1.corpus_digest == e2.corpus_digest

    def test_corpus_digest_changes_with_gate_version(self):
        e1 = _entry(_chain("read_env"), gate_version="v1")
        e2 = _entry(_chain("read_env"), gate_version="v2")
        assert e1.corpus_digest != e2.corpus_digest

    def test_corpus_digest_changes_with_capability_set(self):
        e1 = _entry(_chain("read_env"), capability_set_id="alpha")
        e2 = _entry(_chain("read_env"), capability_set_id="beta")
        assert e1.corpus_digest != e2.corpus_digest


# ---------------------------------------------------------------------------
# Record / idempotency
# ---------------------------------------------------------------------------


class TestRecord:
    def test_record_increments_size(self):
        c = PositiveVerdictCorpus(label="t")
        c.record(
            _chain("read_env", "http_post_internal"),
            verdict_action="allow",
            verdict_digest="vd-1",
            gate_version="v1",
            capability_set_id="default",
        )
        assert len(c) == 1

    def test_record_rejects_block(self):
        c = PositiveVerdictCorpus()
        with pytest.raises(AssertionError):
            c.record(
                _chain("read_env"),
                verdict_action="block",
                verdict_digest="vd-1",
                gate_version="v1",
                capability_set_id="default",
            )

    def test_record_is_idempotent_on_duplicate(self):
        c = PositiveVerdictCorpus()
        chain = _chain("read_env", "http_post_internal")
        c.record(
            chain, verdict_action="allow", verdict_digest="vd-1",
            gate_version="v1", capability_set_id="default",
        )
        c.record(
            chain, verdict_action="allow", verdict_digest="vd-1",
            gate_version="v1", capability_set_id="default",
        )
        assert len(c) == 1

    def test_record_appends_when_verdict_digest_differs(self):
        c = PositiveVerdictCorpus()
        chain = _chain("read_env", "http_post_internal")
        c.record(
            chain, verdict_action="allow", verdict_digest="vd-1",
            gate_version="v1", capability_set_id="default",
        )
        c.record(
            chain, verdict_action="allow", verdict_digest="vd-2",
            gate_version="v1", capability_set_id="default",
        )
        assert len(c) == 2

    def test_iteration(self):
        c = PositiveVerdictCorpus()
        c.record(
            _chain("a"), verdict_action="allow", verdict_digest="v1",
            gate_version="v1", capability_set_id="c",
        )
        c.record(
            _chain("b"), verdict_action="allow", verdict_digest="v2",
            gate_version="v1", capability_set_id="c",
        )
        verbs = [list(e.chain)[0]["verb"] for e in c]
        assert verbs == ["a", "b"]


# ---------------------------------------------------------------------------
# chain_seen
# ---------------------------------------------------------------------------


class TestChainSeen:
    def test_seen_returns_true_for_recorded_chain(self):
        c = PositiveVerdictCorpus()
        chain = _chain("read_env", "http_post_internal")
        c.record(
            chain, verdict_action="allow", verdict_digest="vd",
            gate_version="v1", capability_set_id="default",
        )
        assert c.chain_seen(chain) is True

    def test_unseen_chain_returns_false(self):
        c = PositiveVerdictCorpus()
        c.record(
            _chain("a"), verdict_action="allow", verdict_digest="v",
            gate_version="v1", capability_set_id="c",
        )
        assert c.chain_seen(_chain("b")) is False

    def test_filter_by_gate_version(self):
        c = PositiveVerdictCorpus()
        chain = _chain("read_env")
        c.record(
            chain, verdict_action="allow", verdict_digest="vd",
            gate_version="v1", capability_set_id="default",
        )
        c.record(
            chain, verdict_action="allow", verdict_digest="vd",
            gate_version="v2", capability_set_id="default",
        )
        assert c.chain_seen(chain, gate_version="v1") is True
        assert c.chain_seen(chain, gate_version="v2") is True
        assert c.chain_seen(chain, gate_version="v3") is False

    def test_filter_by_capability_set_id(self):
        c = PositiveVerdictCorpus()
        chain = _chain("read_env")
        c.record(
            chain, verdict_action="allow", verdict_digest="vd",
            gate_version="v1", capability_set_id="alpha",
        )
        assert c.chain_seen(chain, capability_set_id="alpha") is True
        assert c.chain_seen(chain, capability_set_id="beta") is False


# ---------------------------------------------------------------------------
# by_capability_set / by_gate / query
# ---------------------------------------------------------------------------


class TestQuery:
    def test_by_capability_set(self):
        c = PositiveVerdictCorpus()
        c.record(
            _chain("a"), verdict_action="allow", verdict_digest="v",
            gate_version="v1", capability_set_id="alpha",
        )
        c.record(
            _chain("b"), verdict_action="allow", verdict_digest="v",
            gate_version="v1", capability_set_id="beta",
        )
        c.record(
            _chain("c"), verdict_action="allow", verdict_digest="v",
            gate_version="v1", capability_set_id="alpha",
        )
        alpha = c.by_capability_set("alpha")
        assert len(alpha) == 2
        assert all(e.capability_set_id == "alpha" for e in alpha)

    def test_by_gate(self):
        c = PositiveVerdictCorpus()
        c.record(
            _chain("a"), verdict_action="allow", verdict_digest="v",
            gate_version="v1", capability_set_id="c",
        )
        c.record(
            _chain("b"), verdict_action="allow", verdict_digest="v",
            gate_version="v2", capability_set_id="c",
        )
        v1 = c.by_gate("v1")
        assert len(v1) == 1
        assert v1[0].gate_version == "v1"

    def test_query_with_shape_match(self):
        c = PositiveVerdictCorpus()
        c.record(
            _chain("read_env", "http_post_internal"),
            verdict_action="allow", verdict_digest="v",
            gate_version="v1", capability_set_id="c",
        )
        c.record(
            _chain("read_env", "http_post_external"),
            verdict_action="allow", verdict_digest="v",
            gate_version="v1", capability_set_id="c",
        )
        matches = c.query(
            capability_set_id="c",
            shape_match=("read_env", "http_post_internal"),
        )
        assert len(matches) == 1
        assert list(matches[0].chain)[1]["verb"] == "http_post_internal"


# ---------------------------------------------------------------------------
# verify_entry: live re-evaluation
# ---------------------------------------------------------------------------


class _MockGate:
    """A minimal mock that returns a verdict with a known digest."""

    def __init__(self, digest):
        self._digest = digest

    def evaluate_chain(self, chain, capability_set=None):
        return _MockVerdict(self._digest)


class _MockVerdict:
    def __init__(self, digest):
        self.digest = digest


class TestVerifyEntry:
    def test_matching_verdict_returns_true(self):
        c = PositiveVerdictCorpus()
        chain = _chain("read_env")
        c.record(
            chain, verdict_action="allow", verdict_digest="vd-match",
            gate_version="v1", capability_set_id="default",
        )
        entry = list(c)[0]
        gate = _MockGate("vd-match")
        assert c.verify_entry(entry, gate, capability_set=None) is True

    def test_diverged_verdict_returns_false(self):
        c = PositiveVerdictCorpus()
        chain = _chain("read_env")
        c.record(
            chain, verdict_action="allow", verdict_digest="vd-old",
            gate_version="v1", capability_set_id="default",
        )
        entry = list(c)[0]
        gate = _MockGate("vd-new")  # gate now returns a different digest
        assert c.verify_entry(entry, gate, capability_set=None) is False

    def test_gate_without_digest_raises(self):
        class _NoDigest:
            def evaluate_chain(self, chain, capability_set=None):
                return object()  # no .digest / .audit_digest

        c = PositiveVerdictCorpus()
        c.record(
            _chain("a"), verdict_action="allow", verdict_digest="v",
            gate_version="v1", capability_set_id="c",
        )
        with pytest.raises(ValueError):
            c.verify_entry(list(c)[0], _NoDigest(), capability_set=None)


# ---------------------------------------------------------------------------
# Skill extraction
# ---------------------------------------------------------------------------


class TestExtractSkills:
    def test_groups_by_shape(self):
        c = PositiveVerdictCorpus()
        c.record(
            _chain("read_env", "http_post_internal"),
            verdict_action="allow", verdict_digest="v1",
            gate_version="v1.0", capability_set_id="c1",
        )
        c.record(
            _chain("read_env", "http_post_internal"),
            verdict_action="allow", verdict_digest="v2",
            gate_version="v1.0", capability_set_id="c1",
        )
        c.record(
            _chain("read_env", "http_post_external"),
            verdict_action="allow", verdict_digest="v3",
            gate_version="v1.0", capability_set_id="c1",
        )
        skills = c.extract_skills()
        assert len(skills) == 2
        shapes = sorted([s.verbs for s in skills])
        assert shapes == [
            ("read_env", "http_post_external"),
            ("read_env", "http_post_internal"),
        ]

    def test_skill_use_count_increments_on_repeated_shape(self):
        c = PositiveVerdictCorpus()
        for i in range(3):
            c.record(
                _chain("read_env", "http_post_internal"),
                verdict_action="allow", verdict_digest=f"v{i}",
                gate_version="v1", capability_set_id="c",
            )
        skills = c.extract_skills()
        assert len(skills) == 1
        assert skills[0].use_count == 3

    def test_find_skill_matches_known_shape(self):
        c = PositiveVerdictCorpus()
        c.record(
            _chain("read_env", "http_post_internal"),
            verdict_action="allow", verdict_digest="v",
            gate_version="v1", capability_set_id="c",
        )
        skill = c.find_skill(("read_env", "http_post_internal"))
        assert skill is not None
        assert skill.use_count == 1

    def test_find_skill_no_match_returns_none(self):
        c = PositiveVerdictCorpus()
        c.record(
            _chain("read_env", "http_post_internal"),
            verdict_action="allow", verdict_digest="v",
            gate_version="v1", capability_set_id="c",
        )
        assert c.find_skill(("read_env", "http_post_external")) is None

    def test_skill_template_shape_matches(self):
        skill = SkillTemplate(
            verbs=("read_env", "http_post_internal"),
            initial_visibility="internal",
            capability_set_id="c",
            gate_version="v1",
            source_digest="abc",
        )
        assert skill.shape_matches(("read_env", "http_post_internal"))
        assert not skill.shape_matches(("read_env", "http_post_external"))
        assert not skill.shape_matches(("read_env",))


# ---------------------------------------------------------------------------
# attach_trip_engine
# ---------------------------------------------------------------------------


class TestTripEngine:
    def test_attach_and_detach(self):
        c = PositiveVerdictCorpus()
        engine = object()  # any sentinel
        c.attach_trip_engine(engine)
        assert c.trip_engine() is engine
        c.detach_trip_engine()
        assert c.trip_engine() is None

    def test_default_is_none(self):
        c = PositiveVerdictCorpus()
        assert c.trip_engine() is None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_to_json_from_json_roundtrip(self):
        c = PositiveVerdictCorpus(label="my-corpus")
        c.record(
            _chain("read_env", "http_post_internal"),
            verdict_action="allow", verdict_digest="v1",
            gate_version="v1.0", capability_set_id="c",
        )
        c.record(
            _chain("read_env", "http_post_external"),
            verdict_action="allow", verdict_digest="v2",
            gate_version="v1.0", capability_set_id="c",
        )
        payload = c.to_json()
        c2 = PositiveVerdictCorpus.from_json(payload)
        assert c2.label == "my-corpus"
        assert len(c2) == 2

    def test_roundtrip_preserves_corpus_digest(self):
        c = PositiveVerdictCorpus()
        c.record(
            _chain("a"), verdict_action="allow", verdict_digest="v",
            gate_version="v1", capability_set_id="c",
        )
        c2 = PositiveVerdictCorpus.from_json(c.to_json())
        e1 = list(c)[0]
        e2 = list(c2)[0]
        assert e1.corpus_digest == e2.corpus_digest

    def test_corpus_identity_digest_order_independent(self):
        c1 = PositiveVerdictCorpus()
        c2 = PositiveVerdictCorpus()
        c1.record(
            _chain("a"), verdict_action="allow", verdict_digest="v",
            gate_version="v1", capability_set_id="c",
        )
        c1.record(
            _chain("b"), verdict_action="allow", verdict_digest="v",
            gate_version="v1", capability_set_id="c",
        )
        c2.record(
            _chain("b"), verdict_action="allow", verdict_digest="v",
            gate_version="v1", capability_set_id="c",
        )
        c2.record(
            _chain("a"), verdict_action="allow", verdict_digest="v",
            gate_version="v1", capability_set_id="c",
        )
        assert _corpus_identity_digest(list(c1)) == _corpus_identity_digest(list(c2))

    def test_different_corpora_have_different_identity_digests(self):
        c1 = PositiveVerdictCorpus()
        c2 = PositiveVerdictCorpus()
        c1.record(
            _chain("a"), verdict_action="allow", verdict_digest="v",
            gate_version="v1", capability_set_id="c",
        )
        c2.record(
            _chain("b"), verdict_action="allow", verdict_digest="v",
            gate_version="v1", capability_set_id="c",
        )
        assert _corpus_identity_digest(list(c1)) != _corpus_identity_digest(list(c2))


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


class TestComputeCorpusDigest:
    def test_deterministic(self):
        d1 = _compute_corpus_digest("cf", "vd", "v1", "c1")
        d2 = _compute_corpus_digest("cf", "vd", "v1", "c1")
        assert d1 == d2

    def test_changes_on_any_field(self):
        base = _compute_corpus_digest("cf", "vd", "v1", "c1")
        assert _compute_corpus_digest("cf2", "vd", "v1", "c1") != base
        assert _compute_corpus_digest("cf", "vd2", "v1", "c1") != base
        assert _compute_corpus_digest("cf", "vd", "v2", "c1") != base
        assert _compute_corpus_digest("cf", "vd", "v1", "c2") != base
