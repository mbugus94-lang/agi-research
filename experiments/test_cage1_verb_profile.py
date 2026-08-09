"""Validation tests for the read-only per-verb CAGE-1 profile adapter."""

from core.cage1_verb_profile import (
    CAGE1_UNATTRIBUTED_VERB,
    build_verb_profile,

    verb_name_from_row,
)


def row(outcome, **extra):
    return {"outcome": outcome, **extra}


def test_uses_explicit_action_identity_and_keeps_missing_identity_visible():
    report = build_verb_profile([
        row("allow", action_type="read"),
        row("reject", verb_name="write"),
        row("hold_pending_human"),
    ], label="fixture")

    assert [p.verb_name for p in report.profiles] == [CAGE1_UNATTRIBUTED_VERB, "read", "write"]
    assert report.n_unattributed == 1
    assert report.profiles[1].admitted_rate == 1.0
    assert report.profiles[2].refusal_rate == 1.0


def test_detail_provenance_is_supported_without_inference_from_prose():
    assert verb_name_from_row({"detail": {"request_action_type": "publish"}}) == "publish"
    assert verb_name_from_row({"rationale": "the publish action was safe"}) == CAGE1_UNATTRIBUTED_VERB


def test_worst_state_and_rates_are_deterministic():
    reports = [
        row("allow", action_type="search"),
        row("hold_pending_evidence", action_type="search"),
        row("reject", action_type="search"),
    ]
    first = build_verb_profile(reports, label="same")
    second = build_verb_profile(list(reversed(reports)), label="same")
    profile = first.profiles[0]

    assert profile.worst_state == "refused"
    assert profile.n_observations == 3
    assert profile.admitted_rate == 1 / 3
    assert abs(profile.non_admitted_rate - 2 / 3) < 1e-12
    assert first.report_digest == second.report_digest


def test_serialization_and_markdown_expose_distribution():
    report = build_verb_profile([
        row("allow", verb_name="read"),
        row("hold_pending_cef", verb_name="read"),
    ])
    payload = report.to_dict()
    assert payload["profiles"][0]["distribution"]["admitted"] == 1
    assert payload["profiles"][0]["distribution"]["quarantined_for_cef"] == 1
    assert "Per-verb CAGE-1 Profile" in report.to_markdown()
    assert "Worst state" in report.to_markdown()
    assert "read" in report.to_markdown()
