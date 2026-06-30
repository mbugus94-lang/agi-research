"""Calibration CLI - recommend Beta priors for the ProbabilisticTripEngine.

The GovernorCircuit's policy depends on a sound (1 - alpha) upper bound on
the trip rate. That bound is tight only when the prior matches the
operator's prior belief about the trip rate.

This CLI takes a target trip rate (e.g. 0.05) and recommends
``(alpha_prior, beta_prior)`` so the *posterior mean* after no
observations matches the target, while leaving the operator's choice of
confidence (i.e. how many "pseudo-observations" the prior is worth).

Usage
-----
::

    # Default: 20 pseudo-observations of confidence
    python -m cli.calibrate --target 0.05

    # Custom confidence
    python -m cli.calibrate --target 0.05 --pseudo-observations 50

    # Sweep multiple confidences
    python -m cli.calibrate --target 0.05 --sweep 10,20,50,100

    # Verify the recommended prior + a given (trips, total) produces
    # the expected upper bound at 1 - alpha = 0.95
    python -m cli.calibrate --target 0.05 --verify 1 20

Design
------
The Beta(alpha, beta) prior has:
    posterior mean = alpha / (alpha + beta)
    posterior "weight" = alpha + beta

To set the mean to a target p with weight w, use:
    alpha = w * p
    beta  = w * (1 - p)

So given ``--target 0.05`` and ``--pseudo-observations 20``, we get:
    alpha = 1.0, beta = 19.0

Why does the prior weight matter?
    A prior with w=20 effectively starts the engine at "we've seen 20
    observations, with the target fraction being trips". The more
    pseudo-observations, the slower new evidence moves the posterior,
    and the tighter the bound becomes for a fixed confidence level.

The recommended defaults are conservative: w=20 means a 5% target prior
is still movable by a handful of strong-evidence observations but won't
flip on a single bad sample. Lower w (e.g. w=5) is more reactive but
yields wider bounds and noisier gate decisions.

Output is JSON (machine-friendly for CI / dashboards).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Allow ``python cli/calibrate.py ...`` from repo root.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


# ---------------------------------------------------------------------------
# Core helpers.
# ---------------------------------------------------------------------------


def _err(message: str) -> Dict[str, str]:
    return {"error": message}


def _validate_target(target: float) -> None:
    if not (0.0 < target < 1.0):
        raise ValueError(f"target must be in (0, 1), got {target}")


def _validate_weight(weight: float) -> None:
    if weight <= 0:
        raise ValueError(f"pseudo-observations must be > 0, got {weight}")


def recommend_prior(target: float, pseudo_observations: float) -> Tuple[float, float]:
    """Return ``(alpha_prior, beta_prior)`` matching a target mean.

    The Beta(alpha, beta) posterior mean is ``alpha / (alpha + beta)`` and
    the effective sample size is ``alpha + beta``.
    """
    _validate_target(target)
    _validate_weight(pseudo_observations)
    alpha = pseudo_observations * target
    beta = pseudo_observations * (1.0 - target)
    return alpha, beta


def recommend_sweep(target: float, weights: Sequence[float]) -> List[Dict[str, Any]]:
    """Return a list of recommendations across multiple weights."""
    rows: List[Dict[str, Any]] = []
    for w in weights:
        if w <= 0:
            continue
        alpha, beta = recommend_prior(target, w)
        rows.append(
            {
                "pseudo_observations": w,
                "alpha_prior": alpha,
                "beta_prior": beta,
                "prior_mean": alpha / (alpha + beta),
            }
        )
    return rows


def _parse_sweep(raw: str) -> List[float]:
    out: List[float] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        out.append(float(chunk))
    return out


# ---------------------------------------------------------------------------
# Subcommand: recommend.
# ---------------------------------------------------------------------------


def cmd_recommend(args: argparse.Namespace) -> int:
    try:
        if args.sweep:
            weights = _parse_sweep(args.sweep)
            rows = recommend_sweep(args.target, weights)
            out: Dict[str, Any] = {
                "target_trip_rate": args.target,
                "sweep": rows,
            }
            print(json.dumps(out, indent=2))
            return 0
        alpha, beta = recommend_prior(args.target, args.pseudo_observations)
        out = {
            "target_trip_rate": args.target,
            "pseudo_observations": args.pseudo_observations,
            "alpha_prior": alpha,
            "beta_prior": beta,
            "prior_mean": alpha / (alpha + beta),
            "notes": (
                "Start the ProbabilisticTripEngine with alpha_prior and beta_prior "
                "from this recommendation. Tune pseudo_observations downward (5-10) "
                "for more reactive priors, upward (50-100) for tighter bounds and "
                "slower movement."
            ),
        }
        print(json.dumps(out, indent=2))
        return 0
    except ValueError as exc:
        print(json.dumps(_err(str(exc))))
        return 2


# ---------------------------------------------------------------------------
# Subcommand: verify.
# ---------------------------------------------------------------------------


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify a prior choice by feeding observed data and printing the bound.

    Imports ProbabilisticTripEngine so the verification uses the same math
    the gate consumes (Clopper-Pearson upper bound at 1 - alpha).
    """
    try:
        from core.cef_probabilistic_verification import (  # noqa: E402
            ProbabilisticTripEngine,
        )
    except ImportError as exc:  # pragma: no cover - import guard
        print(json.dumps(_err(f"could not import ProbabilisticTripEngine: {exc}")))
        return 2
    target = args.target
    pseudo = args.pseudo_observations
    trips, total = args.trips, args.total
    if total <= 0 or trips < 0 or trips > total:
        print(json.dumps(_err("trips must be in [0, total] and total > 0")))
        return 2
    alpha_prior, beta_prior = recommend_prior(target, pseudo)
    engine = ProbabilisticTripEngine(
        alpha_prior=alpha_prior,
        beta_prior=beta_prior,
    )
    # ``update`` accepts TripObservation; we synthesise one per "trip" and
    # one per "non-trip" up to the requested counts.
    try:
        from core.cef_probabilistic_verification import TripObservation  # noqa: E402

        for i in range(trips):
            engine.update(
                TripObservation(tripped=True, source=f"verify-trip-{i}")
            )
        for i in range(total - trips):
            engine.update(
                TripObservation(tripped=False, source=f"verify-ok-{i}")
            )
    except Exception as exc:
        print(json.dumps(_err(f"engine update failed: {exc}")))
        return 2
    out = {
        "target_trip_rate": target,
        "pseudo_observations": pseudo,
        "alpha_prior": alpha_prior,
        "beta_prior": beta_prior,
        "observed_trips": trips,
        "observed_total": total,
        "observed_rate": trips / total if total > 0 else 0.0,
        "engine_summary": engine.summary(),
    }
    print(json.dumps(out, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Argparse wiring.
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.calibrate",
        description="Calibrate Beta priors for the ProbabilisticTripEngine.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_rec = sub.add_parser(
        "recommend",
        help="recommend alpha_prior/beta_prior for a target trip rate",
    )
    p_rec.add_argument(
        "--target",
        type=float,
        required=True,
        help="target trip rate (e.g. 0.05 for 5%%)",
    )
    p_rec.add_argument(
        "--pseudo-observations",
        type=float,
        default=20.0,
        help="prior pseudo-observations (confidence). Default 20.",
    )
    p_rec.add_argument(
        "--sweep",
        default="",
        help="optional comma-separated list of pseudo-observation weights",
    )
    p_rec.set_defaults(func=cmd_recommend)

    p_ver = sub.add_parser(
        "verify",
        help="verify a prior against (trips, total) and print the bound",
    )
    p_ver.add_argument("--target", type=float, required=True)
    p_ver.add_argument("--pseudo-observations", type=float, default=20.0)
    p_ver.add_argument(
        "--trips", type=int, required=True, help="number of trips observed"
    )
    p_ver.add_argument(
        "--total", type=int, required=True, help="total number of observations"
    )
    p_ver.set_defaults(func=cmd_verify)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
