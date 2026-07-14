#!/usr/bin/env python3
"""Positive Verdict Corpus CLI (operator surface, 2026-07-14).

Reads a serialized ``PositiveVerdictCorpus`` (JSON, written by
``PositiveVerdictCorpus.to_json()``) and emits either a human
readable summary or a JSON stats payload.

This is the *inspect* CLI for the positive verdict corpus (the
operator's record of successful chains). The matching *record* CLI
would write a new entry from a live gate verdict; the inspect CLI
is read-only.

Usage::

    python -m cli.pvc_inspect corpus.json
    python -m cli.pvc_inspect corpus.json --top-skills 5
    python -m cli.pvc_inspect corpus.json --json
    python -m cli.pvc_inspect corpus.json --summary

Output (text mode)::

    Corpus: <label>  entries=<n>  digest=<hex8>...
      by gate:  v1.0=n  v1.1=m  ...
      by cap:   default=n  other=m  ...
      top skills (verb-sequence, use-count, cap, gate):
        read_env -> http_post_internal    n  cap  v1.0
        ...

Output (JSON mode)::

    {
      "label": "...",
      "n_total": n,
      "n_by_gate": {...},
      "n_by_capability_set": {...},
      "stats_digest": "hex...",
      "top_skills": [{"verbs": [...], "use_count": n, "capability_set_id": "...", "gate_version": "..."}]
    }
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

from core.positive_verdict_corpus import (
    PositiveVerdictCorpus,
    SkillTemplate,
)


def _format_skill(s: SkillTemplate) -> str:
    return " -> ".join(s.verbs) + f"   count={s.use_count}  cap={s.capability_set_id}  gate={s.gate_version}"


def render_text(corpus: PositiveVerdictCorpus, top_skills: int) -> str:
    stats = corpus.stats()
    lines: List[str] = []
    lines.append(
        f"Corpus: {corpus.label}  entries={stats.n_total}  digest={stats.digest[:12] if stats.digest else 'n/a'}"
    )
    if stats.n_by_gate:
        gate_str = "  ".join(f"{k}={v}" for k, v in sorted(stats.n_by_gate.items()))
        lines.append(f"  by gate:  {gate_str}")
    if stats.n_by_capability_set:
        cap_str = "  ".join(f"{k}={v}" for k, v in sorted(stats.n_by_capability_set.items()))
        lines.append(f"  by cap:   {cap_str}")
    skills = corpus.extract_skills()
    if skills:
        lines.append(f"  top skills ({min(top_skills, len(skills))} of {len(skills)}):")
        for s in skills[:top_skills]:
            lines.append(f"    {_format_skill(s)}")
    return "\n".join(lines)


def render_json(corpus: PositiveVerdictCorpus, top_skills: int) -> Dict[str, Any]:
    stats = corpus.stats()
    skills = corpus.extract_skills()[:top_skills]
    return {
        "label": corpus.label,
        "n_total": stats.n_total,
        "n_allow": stats.n_allow,
        "n_by_gate": dict(stats.n_by_gate),
        "n_by_capability_set": dict(stats.n_by_capability_set),
        "stats_digest": stats.digest,
        "top_skills": [
            {
                "verbs": list(s.verbs),
                "initial_visibility": s.initial_visibility,
                "use_count": s.use_count,
                "capability_set_id": s.capability_set_id,
                "gate_version": s.gate_version,
                "source_digest": s.source_digest,
            }
            for s in skills
        ],
    }


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("corpus_file", help="Path to corpus JSON file (from to_json())")
    p.add_argument("--top-skills", type=int, default=5, help="Number of top skills to show (default 5)")
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    p.add_argument("--summary", action="store_true", help="One-line summary only")
    args = p.parse_args(argv)

    with open(args.corpus_file) as f:
        payload = f.read()
    corpus = PositiveVerdictCorpus.from_json(payload)

    if args.summary:
        stats = corpus.stats()
        print(
            f"corpus entries={stats.n_total} digest={stats.digest[:12] if stats.digest else 'n/a'}"
        )
        return 0

    if args.json:
        print(json.dumps(render_json(corpus, args.top_skills), indent=2, sort_keys=True))
    else:
        print(render_text(corpus, args.top_skills))
    return 0


if __name__ == "__main__":
    sys.exit(main())
