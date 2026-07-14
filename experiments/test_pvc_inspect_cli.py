"""Tests for the positive verdict corpus CLI (2026-07-14 build)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

import pytest

from core.positive_verdict_corpus import PositiveVerdictCorpus


def _build_corpus_json(tmpdir: str) -> str:
    """Build a small corpus and return the JSON file path."""
    c = PositiveVerdictCorpus(label="cli-test")
    c.record(
        [{"verb": "read_env"}, {"verb": "http_post_internal"}],
        verdict_action="allow",
        verdict_digest="v1",
        gate_version="v1.0",
        capability_set_id="default",
    )
    c.record(
        [{"verb": "read_env"}, {"verb": "http_post_internal"}],
        verdict_action="allow",
        verdict_digest="v2",
        gate_version="v1.0",
        capability_set_id="default",
    )
    c.record(
        [{"verb": "read_secret_store"}],
        verdict_action="allow",
        verdict_digest="v3",
        gate_version="v1.0",
        capability_set_id="default",
    )
    path = os.path.join(tmpdir, "corpus.json")
    with open(path, "w") as f:
        f.write(c.to_json())
    return path


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "cli.pvc_inspect", *args]
    return subprocess.run(
        cmd,
        cwd="/home/workspace/agi-research",
        capture_output=True,
        text=True,
        check=False,
    )


class TestSummaryPath:
    def test_summary_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _build_corpus_json(tmpdir)
            r = _run_cli(path, "--summary")
            assert r.returncode == 0
            assert "entries=3" in r.stdout
            assert "digest=" in r.stdout


class TestTextMode:
    def test_text_mode_lists_top_skills(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _build_corpus_json(tmpdir)
            r = _run_cli(path, "--top-skills", "5")
            assert r.returncode == 0
            assert "Corpus: cli-test" in r.stdout
            assert "read_env -> http_post_internal" in r.stdout
            assert "count=2" in r.stdout

    def test_text_mode_respects_top_skills(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _build_corpus_json(tmpdir)
            r = _run_cli(path, "--top-skills", "1")
            assert r.returncode == 0
            assert "top skills (1 of 2)" in r.stdout

    def test_text_mode_shows_by_gate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _build_corpus_json(tmpdir)
            r = _run_cli(path)
            assert r.returncode == 0
            assert "by gate:" in r.stdout
            assert "by cap:" in r.stdout


class TestJsonMode:
    def test_json_mode_is_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _build_corpus_json(tmpdir)
            r = _run_cli(path, "--json")
            assert r.returncode == 0
            data = json.loads(r.stdout)
            assert data["label"] == "cli-test"
            assert data["n_total"] == 3
            assert len(data["top_skills"]) == 2
            top = data["top_skills"][0]
            assert "read_env" in top["verbs"]

    def test_json_top_skills_respects_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _build_corpus_json(tmpdir)
            r = _run_cli(path, "--json", "--top-skills", "1")
            assert r.returncode == 0
            data = json.loads(r.stdout)
            assert len(data["top_skills"]) == 1

    def test_json_includes_digest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _build_corpus_json(tmpdir)
            r = _run_cli(path, "--json")
            assert r.returncode == 0
            data = json.loads(r.stdout)
            assert "stats_digest" in data
            assert len(data["stats_digest"]) == 64  # SHA-256 hex


class TestErrorPaths:
    def test_missing_file_exits_nonzero(self):
        r = _run_cli("/tmp/does-not-exist-pvc-12345.json")
        # FileNotFoundError traceback; allow nonzero return.
        assert r.returncode != 0
