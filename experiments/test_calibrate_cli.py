"""
Tests for the calibration CLI (cli/calibrate.py).

Coverage
--------
- TestRecommendPrior (4): default weight, custom weight, target=0 -> error,
  target=1 -> error, negative weight -> error
- TestRecommendSweep (2): sweep parses correctly, sweep skips invalid
- TestCmdRecommend (4): no sweep, with sweep, target out of range -> exit 2,
  pseudo_observations <= 0 -> exit 2
- TestCmdVerify (3): import missing -> exit 2, normal verify produces
  engine summary, invalid trips/total -> exit 2
- TestCLISubprocess (2): help text, recommend with default args
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import cli.calibrate as cli_cal  # noqa: E402


class TestRecommendPrior(unittest.TestCase):
    def test_default_weight_20(self):
        a, b = cli_cal.recommend_prior(0.05, 20.0)
        self.assertAlmostEqual(a, 1.0)
        self.assertAlmostEqual(b, 19.0)

    def test_custom_weight(self):
        a, b = cli_cal.recommend_prior(0.10, 50.0)
        self.assertAlmostEqual(a, 5.0)
        self.assertAlmostEqual(b, 45.0)

    def test_target_zero_invalid(self):
        with self.assertRaises(ValueError):
            cli_cal.recommend_prior(0.0, 20.0)

    def test_target_one_invalid(self):
        with self.assertRaises(ValueError):
            cli_cal.recommend_prior(1.0, 20.0)

    def test_negative_weight_invalid(self):
        with self.assertRaises(ValueError):
            cli_cal.recommend_prior(0.05, -1.0)

    def test_posterior_mean_matches_target(self):
        for target in (0.01, 0.05, 0.10, 0.25, 0.50):
            a, b = cli_cal.recommend_prior(target, 20.0)
            self.assertAlmostEqual(a / (a + b), target, places=6)


class TestRecommendSweep(unittest.TestCase):
    def test_sweep_parses(self):
        rows = cli_cal.recommend_sweep(0.05, [10.0, 20.0, 50.0])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["pseudo_observations"], 10.0)
        self.assertEqual(rows[1]["alpha_prior"], 1.0)

    def test_sweep_skips_invalid(self):
        rows = cli_cal.recommend_sweep(0.05, [20.0, -1.0, 0.0])
        # -1 and 0 are dropped
        self.assertEqual(len(rows), 1)


class TestCmdRecommend(unittest.TestCase):
    def test_no_sweep(self):
        ns = _ns(target=0.05, pseudo_observations=20.0, sweep="")
        with redirect_stdout(io.StringIO()) as out:
            rc = cli_cal.cmd_recommend(ns)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["target_trip_rate"], 0.05)
        self.assertEqual(payload["alpha_prior"], 1.0)
        self.assertEqual(payload["beta_prior"], 19.0)

    def test_with_sweep(self):
        ns = _ns(target=0.05, pseudo_observations=20.0, sweep="10,20,50")
        with redirect_stdout(io.StringIO()) as out:
            rc = cli_cal.cmd_recommend(ns)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(len(payload["sweep"]), 3)

    def test_target_out_of_range(self):
        ns = _ns(target=0.0, pseudo_observations=20.0, sweep="")
        with redirect_stdout(io.StringIO()) as out:
            rc = cli_cal.cmd_recommend(ns)
        self.assertEqual(rc, 2)
        self.assertIn("error", json.loads(out.getvalue()))

    def test_negative_pseudo_observations(self):
        ns = _ns(target=0.05, pseudo_observations=-1.0, sweep="")
        with redirect_stdout(io.StringIO()) as out:
            rc = cli_cal.cmd_recommend(ns)
        self.assertEqual(rc, 2)
        self.assertIn("error", json.loads(out.getvalue()))


class TestCmdVerify(unittest.TestCase):
    def test_normal_verify(self):
        ns = _ns(
            target=0.05,
            pseudo_observations=20.0,
            trips=3,
            total=20,
        )
        with redirect_stdout(io.StringIO()) as out:
            rc = cli_cal.cmd_verify(ns)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["observed_trips"], 3)
        self.assertEqual(payload["observed_total"], 20)
        self.assertIn("engine_summary", payload)

    def test_invalid_trips_total(self):
        ns = _ns(
            target=0.05,
            pseudo_observations=20.0,
            trips=10,
            total=5,
        )
        with redirect_stdout(io.StringIO()) as out:
            rc = cli_cal.cmd_verify(ns)
        self.assertEqual(rc, 2)
        self.assertIn("error", json.loads(out.getvalue()))

    def test_zero_total(self):
        ns = _ns(
            target=0.05,
            pseudo_observations=20.0,
            trips=0,
            total=0,
        )
        with redirect_stdout(io.StringIO()) as out:
            rc = cli_cal.cmd_verify(ns)
        self.assertEqual(rc, 2)


class TestParseSweep(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(cli_cal._parse_sweep("10,20,30"), [10.0, 20.0, 30.0])

    def test_with_spaces(self):
        self.assertEqual(cli_cal._parse_sweep("10, 20 , 30"), [10.0, 20.0, 30.0])

    def test_empty(self):
        self.assertEqual(cli_cal._parse_sweep(""), [])


class TestCLISubprocess(unittest.TestCase):
    def test_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "cli.calibrate", "--help"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("recommend", result.stdout)
        self.assertIn("verify", result.stdout)

    def test_recommend_default(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.calibrate",
                "recommend",
                "--target",
                "0.05",
            ],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["alpha_prior"], 1.0)


def _ns(**kwargs):
    class NS:
        pass

    ns = NS()
    for k, v in kwargs.items():
        setattr(ns, k, v)
    return ns


if __name__ == "__main__":
    unittest.main()