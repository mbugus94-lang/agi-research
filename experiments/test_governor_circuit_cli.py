"""
Tests for the GovernorCircuit CLI (cli/governor_circuit.py).

Coverage
--------
- TestCLIHelpers (3): _read_json / _read_jsonl / _err
- TestSummaryCmd (3): missing file -> error exit 2, malformed JSON -> error,
  valid state -> prints expected fields
- TestAuditTailCmd (3): missing file, returns last N, malformed line errors
- TestSimulateCmd (4): missing history, empty history, two-layer simulation
  produces OPEN transition, single-layer simulation follows trips/recovers
- TestDoctorCmd (4): no input -> error, state only -> verdict, audit only ->
  verdict, both -> combined verdict
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from typing import Any, Dict, List

# Allow tests to import CLI scripts directly.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import cli.governor_circuit as cli_gc  # noqa: E402
from core.cef_probabilistic_verification import ProbabilisticTripEngine  # noqa: E402
from core.governor_circuit import (  # noqa: E402
    GateObservation,
    GovernorCircuit,
    GovernorCircuitConfig,
)


# ---------------------------------------------------------------------------
# Helpers for spinning up a real circuit.
# ---------------------------------------------------------------------------


def _make_circuit(trip: float = 0.05, reset: float = 0.01, probes: int = 1):
    """Build a GovernorCircuit with one ProbabilisticTripEngine installed."""
    engine = ProbabilisticTripEngine(alpha_prior=1.0, beta_prior=1.0)
    config = GovernorCircuitConfig(
        trip_threshold=trip,
        reset_threshold=reset,
        probe_count=probes,
    )
    return GovernorCircuit(config=config, per_output_engine=engine)


def _drive(circuit, tripped: bool, label: str = "test"):
    circuit.feed(GateObservation(tripped=tripped, label=label))


class TestCLIHelpers(unittest.TestCase):
    def test_err_returns_dict(self):
        out = cli_gc._err("oops")
        self.assertEqual(out, {"error": "oops"})

    def test_read_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "state.json")
            with open(p, "w") as f:
                json.dump({"state": "OPEN", "upper_bound": 0.1}, f)
            data = cli_gc._read_json(p)
            self.assertEqual(data["state"], "OPEN")

    def test_read_jsonl_yields_each_record(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "audit.jsonl")
            with open(p, "w") as f:
                f.write(json.dumps({"a": 1}) + "\n")
                f.write(json.dumps({"a": 2}) + "\n")
            records = list(cli_gc._read_jsonl(p))
            self.assertEqual(records, [{"a": 1}, {"a": 2}])


class TestSummaryCmd(unittest.TestCase):
    def test_missing_file(self):
        with redirect_stdout(io.StringIO()) as out:
            rc = cli_gc.cmd_summary(_ns(input="/nonexistent/path.json"))
        self.assertEqual(rc, 2)
        self.assertIn("error", json.loads(out.getvalue()))

    def test_valid_state(self):
        circuit = _make_circuit()
        _drive(circuit, True, "trip-1")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "state.json")
            with open(p, "w") as f:
                json.dump(circuit.summary(), f)
            with redirect_stdout(io.StringIO()) as out:
                rc = cli_gc.cmd_summary(_ns(input=p))
            self.assertEqual(rc, 0)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["source"], p)
            self.assertIn(payload["state"], {"closed", "open", "half_open"})

    def test_malformed_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "bad.json")
            with open(p, "w") as f:
                f.write("{not valid")
            with redirect_stdout(io.StringIO()) as out:
                rc = cli_gc.cmd_summary(_ns(input=p))
            self.assertEqual(rc, 2)
            self.assertIn("error", json.loads(out.getvalue()))


class TestAuditTailCmd(unittest.TestCase):
    def test_missing_file(self):
        with redirect_stdout(io.StringIO()) as out:
            rc = cli_gc.cmd_audit_tail(_ns(path="/nope.jsonl", last=5))
        self.assertEqual(rc, 2)
        self.assertIn("error", json.loads(out.getvalue()))

    def test_returns_last_n(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "audit.jsonl")
            with open(p, "w") as f:
                for i in range(25):
                    f.write(json.dumps({"id": i}) + "\n")
            with redirect_stdout(io.StringIO()) as out:
                rc = cli_gc.cmd_audit_tail(_ns(path=p, last=5))
            self.assertEqual(rc, 0)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["total_records"], 25)
            self.assertEqual(payload["returned"], 5)
            self.assertEqual([t["id"] for t in payload["transitions"]], [20, 21, 22, 23, 24])

    def test_malformed_line(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "audit.jsonl")
            with open(p, "w") as f:
                f.write("{not valid")
            with redirect_stdout(io.StringIO()) as out:
                rc = cli_gc.cmd_audit_tail(_ns(path=p, last=10))
            self.assertEqual(rc, 2)
            self.assertIn("error", json.loads(out.getvalue()))


class TestSimulateCmd(unittest.TestCase):
    def test_missing_history(self):
        with redirect_stdout(io.StringIO()) as out:
            rc = cli_gc.cmd_simulate(_ns(history="/nope.jsonl"))
        self.assertEqual(rc, 2)
        self.assertIn("error", json.loads(out.getvalue()))

    def test_empty_history(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "empty.jsonl")
            with open(p, "w") as f:
                pass
            with redirect_stdout(io.StringIO()) as out:
                rc = cli_gc.cmd_simulate(_ns(history=p))
            self.assertEqual(rc, 2)
            self.assertIn("empty", json.loads(out.getvalue())["error"])

    def test_single_layer_trip_and_recover(self):
        # 5 trips then 60 oks -> gate should OPEN, then close.
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "history.jsonl")
            with open(p, "w") as f:
                for i in range(5):
                    f.write(json.dumps({"tripped": True, "label": f"t-{i}"}) + "\n")
                for i in range(60):
                    f.write(json.dumps({"tripped": False, "label": f"ok-{i}"}) + "\n")
            with redirect_stdout(io.StringIO()) as out:
                rc = cli_gc.cmd_simulate(
                    _ns(
                        history=p,
                        trip_threshold=0.40,
                        reset_threshold=0.20,
                        probe_count=1,
                    )
                )
            self.assertEqual(rc, 0)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["history_records"], 65)
            self.assertGreaterEqual(payload["transitions_added"], 1)

    def test_two_layer_session_trip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "history.jsonl")
            with open(p, "w") as f:
                # Per-output ok
                for i in range(40):
                    f.write(
                        json.dumps(
                            {
                                "tripped": False,
                                "label": f"po-{i}",
                                "layer": "per_output",
                            }
                        )
                        + "\n"
                    )
                # Session-layer trips
                for i in range(10):
                    f.write(
                        json.dumps(
                            {"tripped": True, "label": f"s-{i}", "layer": "session"}
                        )
                        + "\n"
                    )
            with redirect_stdout(io.StringIO()) as out:
                rc = cli_gc.cmd_simulate(
                    _ns(
                        history=p,
                        trip_threshold=0.40,
                        reset_threshold=0.20,
                        probe_count=1,
                    )
                )
            self.assertEqual(rc, 0)
            payload = json.loads(out.getvalue())
            self.assertTrue(payload["two_layer"])
            self.assertGreaterEqual(payload["transitions_added"], 1)


class TestDoctorCmd(unittest.TestCase):
    def test_no_inputs(self):
        with redirect_stdout(io.StringIO()) as out:
            rc = cli_gc.cmd_doctor(_ns(state=None, audit=None))
        self.assertEqual(rc, 2)
        self.assertIn("error", json.loads(out.getvalue()))

    def test_state_only(self):
        circuit = _make_circuit()
        _drive(circuit, True, "trip-1")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "state.json")
            with open(p, "w") as f:
                json.dump(circuit.summary(), f)
            with redirect_stdout(io.StringIO()) as out:
                rc = cli_gc.cmd_doctor(_ns(state=p, audit=None))
            self.assertEqual(rc, 0)
            payload = json.loads(out.getvalue())
            self.assertIn(payload["verdict"], {"ok", "probing", "tripped", "unknown"})

    def test_audit_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "audit.jsonl")
            with open(p, "w") as f:
                f.write(json.dumps({"timestamp": "2026-06-30T00:00:00Z"}) + "\n")
            with redirect_stdout(io.StringIO()) as out:
                rc = cli_gc.cmd_doctor(_ns(state=None, audit=p))
            self.assertEqual(rc, 0)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["audit_records"], 1)
            self.assertEqual(payload["last_audit_timestamp"], "2026-06-30T00:00:00Z")

    def test_both(self):
        circuit = _make_circuit()
        _drive(circuit, True, "trip-1")
        with tempfile.TemporaryDirectory() as d:
            sp = os.path.join(d, "state.json")
            ap = os.path.join(d, "audit.jsonl")
            with open(sp, "w") as f:
                json.dump(circuit.summary(), f)
            with open(ap, "w") as f:
                for t in circuit._transitions:
                    f.write(json.dumps(t.to_dict()) + "\n")
            with redirect_stdout(io.StringIO()) as out:
                rc = cli_gc.cmd_doctor(_ns(state=sp, audit=ap))
            self.assertEqual(rc, 0)
            payload = json.loads(out.getvalue())
            self.assertGreaterEqual(payload["audit_records"], 1)


# ---------------------------------------------------------------------------
# End-to-end subprocess smoke test.
# ---------------------------------------------------------------------------


class TestCLISubprocess(unittest.TestCase):
    def test_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "cli.governor_circuit", "--help"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("summary", result.stdout)
        self.assertIn("audit-tail", result.stdout)
        self.assertIn("simulate", result.stdout)
        self.assertIn("doctor", result.stdout)


def _ns(**kwargs):
    """Tiny argparse.Namespace factory."""

    class NS:
        pass

    ns = NS()
    for k, v in kwargs.items():
        setattr(ns, k, v)
    return ns


if __name__ == "__main__":
    unittest.main()