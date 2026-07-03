"""Tests for cli/policy_review.py — VerbPolicyBundle audit review CLI.

Builds on the 2026-07-03 VerbPolicyBundle work.
"""

import io
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

from cli import policy_review
from core.verb_policy_bundle import (
    VerbPolicyAuditLog,
    VerbPolicyBundle,
    VerbPolicyEntry,
    create_verb_policy_bundle,
)
from core.typed_verb_cef_guard import VerbCEFGuardConfig, VerbGuardAction


def _strict_config():
    return VerbCEFGuardConfig(
        low_action=VerbGuardAction.ESCALATE,
        medium_action=VerbGuardAction.ESCALATE,
        high_action=VerbGuardAction.ESCALATE,
        critical_action=VerbGuardAction.ESCALATE,
    )


def _lax_config():
    return VerbCEFGuardConfig(
        low_action=VerbGuardAction.LOG,
        medium_action=VerbGuardAction.LOG,
        high_action=VerbGuardAction.LOG,
        critical_action=VerbGuardAction.LOG,
    )


def test_review_bundle_with_no_events():
    bundle = create_verb_policy_bundle(library_id="cli-test-1")
    summary = policy_review.review_bundle(bundle)
    assert summary["bundle_id"] == "cli-test-1"
    assert summary["n_entries"] == 0
    assert summary["counts_by_source"] == {}


def test_review_bundle_with_register_event():
    bundle = create_verb_policy_bundle(library_id="cli-test-2")
    bundle.register(VerbPolicyEntry(verb_name="pay", verb_version="1.0.0", config=_strict_config()))
    summary = policy_review.review_bundle(bundle)
    assert summary["n_entries"] >= 1
    assert summary["head_hash"] is not None


def test_review_bundle_with_last_n():
    bundle = create_verb_policy_bundle(library_id="cli-test-3")
    bundle.register(VerbPolicyEntry(verb_name="pay", verb_version="*", config=_strict_config()))
    bundle.register(VerbPolicyEntry(verb_name="read", verb_version="*", config=_lax_config()))
    summary = policy_review.review_bundle(bundle, last=1)
    assert summary["n_entries"] == 1


def test_review_jsonl_file_not_found():
    summary = policy_review.review_jsonl("/nonexistent/path/audit.jsonl")
    assert "error" in summary


def test_review_jsonl_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "audit.jsonl")
        events = [
            {"event_kind": "resolve", "verb_name": "pay", "verb_version": "1.0.0", "source": "specific"},
            {"event_kind": "fallback", "verb_name": "read", "verb_version": "1.0.0", "source": "default"},
            {"event_kind": "fallback", "verb_name": "search", "verb_version": "1.0.0", "source": "default"},
        ]
        with open(path, "w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
        summary = policy_review.review_jsonl(path)
        assert summary["n_entries"] == 3
        assert summary["counts_by_source"]["specific"] == 1
        assert summary["counts_by_source"]["default"] == 2


def test_review_jsonl_file_last_n():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "audit.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for i in range(10):
                e = {"event_kind": "resolve", "verb_name": f"v{i}", "source": "specific"}
                f.write(json.dumps(e) + "\n")
        summary = policy_review.review_jsonl(path, last=3)
        assert summary["n_entries"] == 3


def test_print_summary_runs(capsys):
    summary = {
        "bundle_id": "x",
        "n_entries": 5,
        "counts_by_source": {"specific": 3, "default": 2},
        "head_hash": "a" * 64,
        "chain_valid": True,
        "last_events": [
            {"event_kind": "resolve", "verb_name": "pay", "verb_version": "1.0.0", "source": "specific"},
        ],
    }
    policy_review.print_summary(summary)
    captured = capsys.readouterr()
    assert "Bundle: x" in captured.out
    assert "Entries: 5" in captured.out
    assert "specific" in captured.out
    assert "Chain valid" in captured.out


def test_print_summary_jsonl(capsys):
    summary = {
        "file": "/tmp/audit.jsonl",
        "n_entries": 2,
        "counts_by_source": {"specific": 1, "default": 1},
        "last_events": [],
    }
    policy_review.print_summary(summary)
    captured = capsys.readouterr()
    assert "File:" in captured.out


def test_main_jsonl_mode(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "audit.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"event_kind": "resolve", "verb_name": "pay", "source": "specific"}) + "\n")
        rc = policy_review.main(["--jsonl", path])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Entries: 1" in captured.out


def test_main_requires_args(capsys):
    with pytest.raises(SystemExit):
        policy_review.main([])
