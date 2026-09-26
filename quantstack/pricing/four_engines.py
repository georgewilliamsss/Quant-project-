"""One European call, four QuantLib pricing engines.

This module demonstrates the idea the "Five Repos, One Engine" article puts
at the centre of the QuantLib layer: **an instrument is a statement of
contractual cash flows; a pricing engine is a swappable numerical strategy
for valuing it.**  QuantLib keeps those two concerns in separate objects on
purpose.  We build exactly ONE ``ql.VanillaOption`` for the brief's market
setup (see :func:`build_option`) and never construct a second one for it.
Every number in the convergence table comes from calling
``option.setPricingEngine(...)`` followed by ``option.NPV()`` on that same
Python object.

That claim is checked, not just stated.  Every result row records
``id(option)`` for the object it was actually priced on (see :func:`_row`),
and :func:`check_single_instrument` requires that all rows carry the id of
the one live instrument that :func:`main` built.  A ladder that quietly
built its own option would write a different id and fail the check.
``tests/test_pricing.py`` also counts ``ql.VanillaOption`` constructions
and asserts there is exactly one.

Engines used, in increasing order of "there is no closed form, so we have to
approximate":

1. ``AnalyticEuropeanEngine``       -- closed-form Black-Scholes-Merton.
2. ``BinomialVanillaEngine("crr")`` -- Cox-Ross-Rubinstein binomial tree,
   refined over a ladder of step counts.
3. ``FdBlackScholesVanillaEngine``  -- finite-difference PDE solver (Douglas
   ADI scheme, the QuantLib default), refined over a ladder of grid sizes.
4. ``MCEuropeanEngine("pr")``       -- Monte Carlo with a pseudo-random
   sequence, refined over a ladder of sample counts, fixed seed for
   reproducibility.  It is checked *statistically*, against QuantLib's own
   ``errorEstimate()``; see "Monte Carlo accuracy" below.

   The same ``MCEuropeanEngine`` is also run with ``"ld"`` (a Sobol
   low-discrepancy sequence), labelled ``mc_sobol``.  It is a variant of
   engine 4, not a fifth method.  It is the honest way to get a *tight*,
   seed-independent Monte Carlo check.

Market data (fixed so the run is reproducible)
-----------------------------------------------
Spot 100, strike 100, flat vol 20%, flat risk-free 2% continuously
compounded (``ql.FlatForward``), no dividends, 1Y tenor, ``ql.Actual365Fixed``
day count on every curve, evaluation date fixed at 2026-01-15 (expiry
2027-01-15, so T = 365/365 = 1.0 exactly).  The actual year fraction is
written to ``results/pricing_summary.json``.

Why our numbers differ from the article's (and how we reproduce them)
----------------------------------------------------------------------
The article quotes 8.9294 (analytic), 8.9288 (tree), 8.9295 (FD) and
8.9292 (MC).  At the brief's date, T = 1.0 and the textbook closed form is

    d1 = (ln(S/K) + (r + sigma^2/2) T) / (sigma sqrt(T)) = 0.2
    d2 = d1 - sigma sqrt(T)                              = 0.0
    C  = S N(d1) - K e^{-rT} N(d2)                       = 8.916037...

``AnalyticEuropeanEngine`` returns exactly that (an independent erf-based
closed form in the tests agrees to ~1e-15).  So the engine does not cause
the gap.  The option life does.

The article's numbers are this same contract with a **366-day** life.  If
the evaluation date's one-year period contains 29 February, for example
2024-01-15 to 2025-01-15, then Act/365F gives T = 366/365 = 1.0027397.  At
that date this module's own code path (:func:`article_setup_repro`, again
one instrument with four engines swapped onto it) gives:

    analytic 8.929429   (article 8.9294)
    CRR-3200 8.928806   (article 8.9288)
    FD-800   8.929508   (article 8.9295)
    MC-1e6   8.928845   (article 8.9292; 0.0004 apart, SE ~0.0138)

The first three match to 4dp.  The MC price is about 0.03 standard errors
from the article's figure, which is as close as two MC runs with different
random streams can be expected to agree.

This is not a day-count mismatch, and it is not a QuantLib version issue.
An earlier version of this docstring blamed an Actual360 discount curve
paired with an Actual365Fixed vol curve.  That is wrong.  That setup gives
8.929657 analytic, which is 8.9297 at 4dp, not 8.9294.  It also cannot
explain the tree and FD numbers.  Those engines take T from the risk-free
curve's day counter (``BlackScholesMertonProcess::time``), so under that
setup CRR-3200 gives 8.983140 and FD-800 gives 8.983846.

We keep the brief's 2026-01-15 date as the main run and measure every
``abs_error`` against *its* analytic price, 8.916037.  The 2024 run is
reported separately under ``article_setup_repro`` in the summary JSON.

Monte Carlo accuracy (read before trusting an MC abs_error)
-----------------------------------------------------------
With pseudo-random paths, the error at N samples is a random draw whose
spread is the standard error, SE ~ sigma_payoff / sqrt(N).  QuantLib reports
it as ``option.errorEstimate()``.  For this contract SE is about 0.0617 at
50k samples and about 0.0138 at 1e6.  A fixed 0.001 tolerance at 1e6 is
therefore about 0.07 SE, which a fresh seed meets only ~6% of the time.
Seed 42 happens to land at 0.00058, which is 0.04 SE.  That is luck, not
convergence, and the article's own 0.0002 MC gap is luck in the same way.
So the pseudo-random engine is asserted against ``abs_error <
MC_SE_MULTIPLE * std_error``.  That check holds for any seed about 99.7%
of the time, and the tests confirm it over 20 seeds.  The fixed
``FINEST_TOL`` applies to the tree, the FD grid and the Sobol run, which are
deterministic.
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from quantstack._swig_order import ensure_ore_before_quantlib

ensure_ore_before_quantlib()  # ORE (if installed) must load before QuantLib: see quantstack/_swig_order.py
import QuantLib as ql  # noqa: E402

# --------------------------------------------------------------------------
# Fixed contract & market data
# --------------------------------------------------------------------------

EVAL_DATE = ql.Date(15, 1, 2026)
SPOT = 100.0
STRIKE = 100.0
VOL = 0.20
RATE = 0.02
DAY_COUNTER = ql.Actual365Fixed()
CALENDAR = ql.TARGET()
MATURITY_TENOR = ql.Period(1, ql.Years)

# The article's numbers correspond to a 1Y option whose life spans 29 Feb
# (T = 366/365 under Act/365F).  2024-01-15 -> 2025-01-15 is one such
# period; see the module docstring and article_setup_repro().
ARTICLE_EVAL_DATE = ql.Date(15, 1, 2024)

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"

# Refinement ladders.  The finest tree / FD / Sobol levels clear FINEST_TOL
# deterministically.  The pseudo-random MC ladder is judged against its
# standard error instead (see module docstring).  tests/test_pricing.py uses
# cheaper checkpoints: crr steps=300, fd grid=100, mc samples=50_000 (pr) and
# 10_000 / 100_000 (Sobol).
TREE_STEPS_LADDER = [50, 100, 200, 400, 800, 1600, 3200]
FD_GRID_LADDER = [10, 20, 50, 100, 200, 400, 800]
MC_SAMPLES_LADDER = [1_000, 10_000, 50_000, 100_000, 500_000, 1_000_000]
MC_SEED = 42  # fixes the pseudo-random stream so the run is bit-for-bit reproducible

# The article claims the finest level of each numerical engine lands within
# 0.0007 of analytic.  We assert 0.001 for the deterministic engines (tree,
# FD, Sobol MC).  For pseudo-random MC a fixed tolerance that small is not
# attainable in expectation at 1e6 samples (SE ~0.0138), so that engine is
# held to abs_error < MC_SE_MULTIPLE * std_error instead.
FINEST_TOL = 0.001
MC_SE_MULTIPLE = 3.0

ARTICLE_REFERENCE = {
    "analytic": 8.9294,
    "binomial_crr": 8.9288,
    "fd_black_scholes": 8.9295,
    "mc_pseudo_random": 8.9292,
}

NUMERICAL_ENGINES = ("binomial_crr", "fd_black_scholes", "mc_pseudo_random", "mc_sobol")
CSV_COLUMNS = ["engine", "level", "price", "abs_error", "std_error", "seconds"]


def maturity_date(eval_date: ql.Date = EVAL_DATE) -> ql.Date:
    """Expiry of the option for a given evaluation date (eval date + 1Y)."""
    return eval_date + MATURITY_TENOR


def year_fraction(eval_date: ql.Date = EVAL_DATE) -> float:
    """Actual365Fixed year fraction from ``eval_date`` to expiry.

    This is the T every engine prices with, because the engines read time
    off the risk-free curve's day counter, which is ``DAY_COUNTER`` here.
    It is 1.0 for the brief's date and 366/365 for the article's.
    """
    return DAY_COUNTER.yearFraction(eval_date, maturity_date(eval_date))


def build_process(eval_date: ql.Date = EVAL_DATE) -> ql.BlackScholesMertonProcess:
    """Build the market data wrapper QuantLib engines price against.

    Sets the global evaluation date as a side effect, because QuantLib
    engines read ``ql.Settings.instance().evaluationDate`` implicitly.
    Callers that care about global state (tests,
    :func:`article_setup_repro`) save and restore it.
    """
    ql.Settings.instance().evaluationDate = eval_date
    spot_handle = ql.QuoteHandle(ql.SimpleQuote(SPOT))
    rate_ts = ql.YieldTermStructureHandle(ql.FlatForward(eval_date, RATE, DAY_COUNTER))
    div_ts = ql.YieldTermStructureHandle(ql.FlatForward(eval_date, 0.0, DAY_COUNTER))
    vol_ts = ql.BlackVolTermStructureHandle(
        ql.BlackConstantVol(eval_date, CALENDAR, VOL, DAY_COUNTER)
    )
    return ql.BlackScholesMertonProcess(spot_handle, div_ts, rate_ts, vol_ts)


def build_option(eval_date: ql.Date = EVAL_DATE) -> ql.VanillaOption:
    """Construct the ONE instrument object every engine below prices.

    This is the crux of the demonstration.  A ``VanillaOption`` is just a
    ``(payoff, exercise)`` pair: a statement of *what* is owed and *when*.
    It carries no view on *how* to compute a value.  That view is injected
    afterwards, and can be swapped at will, via ``setPricingEngine``.
    Callers must build this exactly once per market setup and reuse it.
    :func:`check_single_instrument` enforces that on the result rows.
    """
    payoff = ql.PlainVanillaPayoff(ql.Option.Call, STRIKE)
    exercise = ql.EuropeanExercise(maturity_date(eval_date))
    return ql.VanillaOption(payoff, exercise)


def _price(option: ql.VanillaOption, engine: ql.PricingEngine) -> tuple[float, float]:
    """Swap ``engine`` onto ``option`` (same object, no rebuild) and time NPV()."""
    option.setPricingEngine(engine)
    t0 = time.perf_counter()
    price = option.NPV()
    elapsed = time.perf_counter() - t0
    return price, elapsed


def _row(
    name: str,
    level: int,
    option: ql.VanillaOption,
    engine: ql.PricingEngine,
    analytic_price: float | None,
    with_std_error: bool = False,
) -> dict[str, Any]:
    """Price ``option`` with ``engine`` and return one result row.

    ``instrument_id`` records ``id(option)`` for the object that was
    actually priced, so :func:`check_single_instrument` can prove afterwards
    that every row came from the same instrument.  ``std_error`` is
    QuantLib's ``errorEstimate()``.  Only pseudo-random MC provides one:
    low-discrepancy sequences raise "error estimate not provided", and the
    tree and FD engines have no statistical error at all.
    """
    price, seconds = _price(option, engine)
    return {
        "engine": name,
        "level": level,
        "price": price,
        "abs_error": 0.0 if analytic_price is None else abs(price - analytic_price),
        "std_error": option.errorEstimate() if with_std_error else None,
        "seconds": seconds,
        "instrument_id": id(option),
    }


def _crr_engine(process: ql.BlackScholesMertonProcess, steps: int) -> ql.PricingEngine:
    return ql.BinomialVanillaEngine(process, "crr", steps)


def _fd_engine(process: ql.BlackScholesMertonProcess, grid: int) -> ql.PricingEngine:
    return ql.FdBlackScholesVanillaEngine(process, grid, grid)


def _mc_engine(process: ql.BlackScholesMertonProcess, samples: int, rng: str = "pr") -> ql.PricingEngine:
    """``MCEuropeanEngine`` with one time step per year.

    One step is exact here.  The payoff depends only on the terminal spot,
    and under GBM a single log-normal step to expiry has no discretisation
    bias.  (For T = 366/365 QuantLib still uses a single step.)  The seed
    only matters for ``"pr"``.  The 1-D Sobol sequence behind ``"ld"`` gives
    identical prices for any seed, so none is passed.
    """
    kwargs: dict[str, Any] = {"timeStepsPerYear": 1, "requiredSamples": samples}
    if rng == "pr":
        kwargs["seed"] = MC_SEED
    return ql.MCEuropeanEngine(process, rng, **kwargs)


def _ladder(
    name: str,
    levels: list[int],
    option: ql.VanillaOption,
    analytic_price: float,
    make_engine: Callable[[int], ql.PricingEngine],
    with_std_error: bool = False,
) -> list[dict[str, Any]]:
    return [
        _row(name, level, option, make_engine(level), analytic_price, with_std_error)
        for level in levels
    ]


def price_analytic(option: ql.VanillaOption, process: ql.BlackScholesMertonProcess) -> dict[str, Any]:
    """Closed-form Black-Scholes-Merton price, the reference for every abs_error below."""
    return _row("analytic", 1, option, ql.AnalyticEuropeanEngine(process), None)


def run_binomial_ladder(
    option: ql.VanillaOption, process: ql.BlackScholesMertonProcess, analytic_price: float
) -> list[dict[str, Any]]:
    """Cox-Ross-Rubinstein binomial tree at increasing step counts.

    ``ql.BinomialVanillaEngine`` is a *Python-level factory function*, not a
    SWIG class.  Reading ``QuantLib.py`` shows it lower-cases the tree-type
    name and dispatches to ``BinomialCRRVanillaEngine``,
    ``BinomialJRVanillaEngine`` and so on, so ``"CRR"`` works as well as
    ``"crr"``.  An unknown name raises ``RuntimeError: unknown binomial
    engine type`` at call time, and there is no static type to catch it.
    That is worth knowing before guessing at the API from an old blog post.
    """
    return _ladder("binomial_crr", TREE_STEPS_LADDER, option, analytic_price, lambda n: _crr_engine(process, n))


def run_fd_ladder(
    option: ql.VanillaOption, process: ql.BlackScholesMertonProcess, analytic_price: float
) -> list[dict[str, Any]]:
    """Finite-difference PDE solver at increasing (square) grid sizes.

    ``FdBlackScholesVanillaEngine(process, tGrid, xGrid)`` defaults to
    ``dampingSteps=0`` and the Douglas ADI scheme.  Both defaults are only
    visible by reading the SWIG-generated ``__init__`` docstring
    (``ext::shared_ptr<...> process, Size tGrid=100, Size xGrid=100, ...
    FdmSchemeDesc schemeDesc=FdmSchemeDesc::Douglas() ...``), because
    ``help()`` on the compiled class gives no signature at all.
    """
    return _ladder("fd_black_scholes", FD_GRID_LADDER, option, analytic_price, lambda n: _fd_engine(process, n))


def run_mc_ladder(
    option: ql.VanillaOption, process: ql.BlackScholesMertonProcess, analytic_price: float
) -> list[dict[str, Any]]:
    """Monte Carlo (pseudo-random) at increasing sample counts, fixed seed.

    Each row carries ``std_error`` from ``option.errorEstimate()``, and that
    column is the thing that converges.  It falls like 1/sqrt(N), from
    ~0.44 at 1k samples to ~0.0138 at 1e6.  The realised ``abs_error`` for
    one fixed stream is a single draw around that bound and is not
    monotone in N.  At seed 42 the 100k run lands further from analytic
    than the 50k run (0.0301 vs 0.0015), and both are well inside 1 SE.  We
    report this as-is.  The figure shows the SE line next to the bouncing
    error line so the reader can see which is which.
    """
    return _ladder(
        "mc_pseudo_random",
        MC_SAMPLES_LADDER,
        option,
        analytic_price,
        lambda n: _mc_engine(process, n, "pr"),
        with_std_error=True,
    )


def run_sobol_ladder(
    option: ql.VanillaOption, process: ql.BlackScholesMertonProcess, analytic_price: float
) -> list[dict[str, Any]]:
    """The same ``MCEuropeanEngine`` driven by a Sobol sequence (``"ld"``).

    This is a labelled quasi-Monte Carlo variant, not a fifth method.  With
    one time step the problem is one-dimensional, and a Sobol sequence
    fills it far more evenly than random draws.  The error falls roughly
    like 1/N instead of 1/sqrt(N), and it does not depend on a seed, so a
    fixed ``FINEST_TOL`` check on it is meaningful.  The price is still
    biased low by ~1e-4 at 1e6 points.  QuantLib gives no error estimate
    for LD sequences.
    """
    return _ladder("mc_sobol", MC_SAMPLES_LADDER, option, analytic_price, lambda n: _mc_engine(process, n, "ld"))


def run_all_engines(
    option: ql.VanillaOption, process: ql.BlackScholesMertonProcess
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Analytic price plus every numerical ladder, all on ``option``.

    This is the code path :func:`main` uses.  Only engines are created in
    here, never instruments.
    """
    analytic_row = price_analytic(option, process)
    analytic_price = analytic_row["price"]
    rows = (
        run_binomial_ladder(option, process, analytic_price)
        + run_fd_ladder(option, process, analytic_price)
        + run_mc_ladder(option, process, analytic_price)
        + run_sobol_ladder(option, process, analytic_price)
    )
    return analytic_row, rows


def check_single_instrument(rows: list[dict[str, Any]], option: ql.VanillaOption) -> int:
    """Raise ``AssertionError`` unless every row was priced on ``option``.

    Comparing against the *live* ``option`` is sound.  While ``option``
    exists, no other Python object can share its ``id``, so a row priced on
    a freshly built instrument always shows a different id, even if that
    instrument has since been garbage-collected.  Returns the number of
    rows checked.
    """
    expected = id(option)
    stray = [(r["engine"], r["level"]) for r in rows if r.get("instrument_id") != expected]
    if stray:
        raise AssertionError(
            f"{len(stray)} row(s) were not priced on the single instrument object: {stray[:5]}"
        )
    return len(rows)


def _finest(rows: list[dict[str, Any]], engine: str) -> dict[str, Any]:
    return [r for r in rows if r["engine"] == engine][-1]


def _finest_check(row: dict[str, Any]) -> tuple[bool, str]:
    """(passed, description) for the finest row of one numerical engine."""
    if row["engine"] == "mc_pseudo_random":
        bound = MC_SE_MULTIPLE * row["std_error"]
        return row["abs_error"] < bound, f"abs_error < {MC_SE_MULTIPLE:g} * std_error (= {bound:.6f})"
    return row["abs_error"] < FINEST_TOL, f"abs_error < {FINEST_TOL}"


def check_finest_levels(rows: list[dict[str, Any]]) -> None:
    """Raise ``AssertionError`` if any engine's finest level misses its check.

    The tree, FD and Sobol runs must be within ``FINEST_TOL`` of analytic.
    Pseudo-random MC must be within ``MC_SE_MULTIPLE`` standard errors, which
    is a check that does not depend on the seed being lucky (module
    docstring).  This uses explicit raises, not ``assert``, so it still runs
    under ``python -O``.
    """
    for name in NUMERICAL_ENGINES:
        row = _finest(rows, name)
        passed, desc = _finest_check(row)
        if not passed:
            raise AssertionError(
                f"{name} finest level {row['level']} failed {desc}: abs_error={row['abs_error']:.6f}"
            )


def article_setup_repro(mc_samples: int = MC_SAMPLES_LADDER[-1]) -> dict[str, Any]:
    """Reproduce the article's four numbers by pricing with a 366-day option life.

    Same pattern as :func:`main`: one instrument for this setup, four engines
    swapped onto it.  The only input that changes is the evaluation date,
    now ``ARTICLE_EVAL_DATE`` (2024-01-15, so expiry is 2025-01-15 and T =
    366/365).  This setup needs its own instrument because its expiry date
    is different.  The global evaluation date is restored on exit.
    ``mc_samples`` can be lowered so tests avoid the 1e6-sample run.
    """
    settings = ql.Settings.instance()
    saved = settings.evaluationDate
    try:
        process = build_process(ARTICLE_EVAL_DATE)
        option = build_option(ARTICLE_EVAL_DATE)
        analytic = price_analytic(option, process)
        a = analytic["price"]
        rows = [
            analytic,
            _row("binomial_crr", TREE_STEPS_LADDER[-1], option, _crr_engine(process, TREE_STEPS_LADDER[-1]), a),
            _row("fd_black_scholes", FD_GRID_LADDER[-1], option, _fd_engine(process, FD_GRID_LADDER[-1]), a),
            _row("mc_pseudo_random", mc_samples, option, _mc_engine(process, mc_samples, "pr"), a, with_std_error=True),
            _row("mc_sobol", mc_samples, option, _mc_engine(process, mc_samples, "ld"), a),
        ]
        check_single_instrument(rows, option)
    finally:
        settings.evaluationDate = saved

    maturity = maturity_date(ARTICLE_EVAL_DATE)
    prices: dict[str, Any] = {}
    for r in rows:
        entry: dict[str, Any] = {"level": r["level"], "price": r["price"]}
        if r["std_error"] is not None:
            entry["std_error"] = r["std_error"]
        prices[r["engine"]] = entry

    diff = {k: prices[k]["price"] - ref for k, ref in ARTICLE_REFERENCE.items()}
    mc = prices["mc_pseudo_random"]
    return {
        "evaluation_date": ARTICLE_EVAL_DATE.ISO(),
        "maturity_date": maturity.ISO(),
        "days": maturity - ARTICLE_EVAL_DATE,
        "year_fraction": year_fraction(ARTICLE_EVAL_DATE),
        "prices": prices,
        "article_reference_prices": ARTICLE_REFERENCE,
        "diff_vs_article": diff,
        "matches_article_4dp": {
            k: abs(round(prices[k]["price"], 4) - ref) < 1e-9 for k, ref in ARTICLE_REFERENCE.items()
        },
        "mc_pseudo_random_diff_in_std_errors": abs(diff["mc_pseudo_random"]) / mc["std_error"],
        "note": (
            "Same contract and market as the main run.  Only the evaluation date moves to "
            "2024-01-15, so the 1Y life spans 29 Feb 2024 and T = 366/365 under Act/365F.  "
            "Analytic, tree and FD match the article at 4dp.  Pseudo-random MC is compared in "
            "standard errors because two MC runs agree only to within SE."
        ),
    }


def schedule_demo() -> dict[str, Any]:
    """A tiny demonstration of the calendar/schedule/day-count "plumbing" the
    article calls irreplaceable.  This part of QuantLib has nothing to do
    with any pricing model and everything to do with getting the *dates*
    right, which is where real trading-desk bugs live.

    Builds a 20y annual schedule on TARGET with the Following convention
    starting 2016-03-01, and computes the day-count fraction of its first
    period under two conventions.  The same two dates can mean two
    different amounts of "time" depending on which desk's convention is
    used.
    """
    start = ql.Date(1, 3, 2016)
    end = start + ql.Period(20, ql.Years)
    schedule = ql.Schedule(
        start,
        end,
        ql.Period(1, ql.Years),
        CALENDAR,
        ql.Following,
        ql.Following,
        ql.DateGeneration.Forward,
        False,
    )
    dates = list(schedule)

    d0, d1 = dates[0], dates[1]
    thirty360 = ql.Thirty360(ql.Thirty360.BondBasis)
    act360 = ql.Actual360()

    return {
        "calendar": "TARGET",
        "convention": "Following",
        "tenor": "20Y annual",
        "count": len(dates),
        "first_dates": [d.ISO() for d in dates[:3]],
        "last_dates": [d.ISO() for d in dates[-3:]],
        "first_period": {"start": d0.ISO(), "end": d1.ISO()},
        "day_count_fraction": {
            "thirty360_bondbasis": thirty360.yearFraction(d0, d1),
            "actual360": act360.yearFraction(d0, d1),
        },
    }


def _gap_explanation(analytic_price: float, repro: dict[str, Any] | None) -> str:
    text = (
        f"Built as the brief specifies (evaluation date {EVAL_DATE.ISO()}, 1Y expiry "
        f"{maturity_date().ISO()}, Actual365Fixed on every curve, so T = {year_fraction():.6f}), "
        f"the closed-form price is {analytic_price:.6f}, not the article's 8.9294.  The gap "
        "comes from the option life, not the engines.  The article's numbers are this same "
        "contract priced with a 366-day life: an evaluation date whose 1Y period contains "
        "29 Feb (e.g. 2024-01-15 -> 2025-01-15) gives T = 366/365 = 1.0027397 under Act/365F."
    )
    if repro is not None:
        p = repro["prices"]
        text += (
            f"  At that date this module reproduces analytic {p['analytic']['price']:.6f}, "
            f"CRR-{p['binomial_crr']['level']} {p['binomial_crr']['price']:.6f} and "
            f"FD-{p['fd_black_scholes']['level']} {p['fd_black_scholes']['price']:.6f}, matching "
            f"the article's 8.9294 / 8.9288 / 8.9295 at 4dp.  MC-{p['mc_pseudo_random']['level']} "
            f"gives {p['mc_pseudo_random']['price']:.6f} vs 8.9292, "
            f"{repro['mc_pseudo_random_diff_in_std_errors']:.2f} standard errors apart "
            "(see article_setup_repro)."
        )
    text += (
        "  It is not a day-count mismatch.  An Actual360 discount curve with an Actual365Fixed "
        "vol curve, an earlier incorrect explanation, gives 8.929657 analytic and ~8.983 for "
        "tree and FD.  Those engines take T from the risk-free curve's day counter.  It is not "
        "a QuantLib version issue either.  All abs_error values in this file are measured "
        f"against the main run's analytic price ({analytic_price:.6f})."
    )
    return text


def write_outputs(
    rows: list[dict[str, Any]],
    analytic_row: dict[str, Any],
    schedule: dict[str, Any],
    article_repro: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write the CSV, JSON summary and PNG this module is required to ship.

    Returns the summary dict that was written to ``pricing_summary.json``.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    all_rows = [analytic_row] + rows
    csv_path = RESULTS_DIR / "pricing_convergence.csv"
    with csv_path.open("w", newline="") as fh:
        # instrument_id is a memory address: it is used for the identity
        # check but kept out of the CSV so reruns stay diffable.
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    engines: dict[str, Any] = {}
    for name in NUMERICAL_ENGINES:
        r = _finest(rows, name)
        passed, desc = _finest_check(r)
        entry: dict[str, Any] = {
            "finest_level": r["level"],
            "finest_price": r["price"],
            "abs_error_vs_analytic": r["abs_error"],
            "seconds": r["seconds"],
            "check": desc,
            "check_passed": passed,
        }
        if r["std_error"] is not None:
            entry["std_error"] = r["std_error"]
            entry["abs_error_in_std_errors"] = r["abs_error"] / r["std_error"]
            entry["within_finest_tolerance"] = r["abs_error"] < FINEST_TOL
            entry["note"] = (
                f"A fixed {FINEST_TOL} tolerance is ~{FINEST_TOL / r['std_error']:.2f} SE at this "
                "sample size and is not attainable in expectation for pseudo-random MC.  If it "
                f"passes, that is because seed {MC_SEED} landed close by chance."
            )
        if name == "mc_sobol":
            entry["note"] = (
                "Same MCEuropeanEngine with a Sobol ('ld') sequence: a labelled quasi-MC "
                "variant of engine 4, deterministic and seed-independent here."
            )
        engines[name] = entry

    ids = {r.get("instrument_id") for r in all_rows}
    analytic_price = analytic_row["price"]
    summary: dict[str, Any] = {
        "quantlib_version": ql.__version__,
        "evaluation_date": EVAL_DATE.ISO(),
        "market": {
            "spot": SPOT,
            "strike": STRIKE,
            "vol": VOL,
            "rate_continuous": RATE,
            "day_counter": DAY_COUNTER.name(),
            "dividends": 0.0,
            "tenor": "1Y",
            "maturity_date": maturity_date().ISO(),
            "year_fraction": year_fraction(),
        },
        "analytic_price": analytic_price,
        "engines": engines,
        "finest_tolerance": FINEST_TOL,
        "mc_se_multiple": MC_SE_MULTIPLE,
        "mc_seed": MC_SEED,
        "article_reference_prices": ARTICLE_REFERENCE,
        "gap_vs_article": {
            name: round(engines[name]["finest_price"] - ARTICLE_REFERENCE[name], 6)
            for name in ("binomial_crr", "fd_black_scholes", "mc_pseudo_random")
        }
        | {"analytic": round(analytic_price - ARTICLE_REFERENCE["analytic"], 6)},
        "gap_explanation": _gap_explanation(analytic_price, article_repro),
        "article_setup_repro": article_repro,
        "instrument_identity": {
            "rows_checked": len(all_rows),
            "distinct_instrument_ids": len(ids),
            "passed": len(ids) == 1,
            "how": (
                "Every row records id() of the VanillaOption it was priced on.  "
                "check_single_instrument() requires one id, that of the single live object "
                "built by build_option(), across the analytic row and all four ladders.  "
                "tests/test_pricing.py also counts VanillaOption constructions."
            ),
        },
        "schedule_demo": schedule,
    }
    json_path = RESULTS_DIR / "pricing_summary.json"
    json_path.write_text(json.dumps(summary, indent=2))

    _plot_convergence(rows)
    return summary


def _plot_convergence(rows: list[dict[str, Any]]) -> None:
    """Abs error vs refinement level, log-log, one line per numerical engine.

    The pseudo-random MC standard error is drawn as a dashed line in the
    same colour.  That line is the quantity that converges, and the solid
    MC line is one random draw scattered around it.
    """
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    # Categorical slots 1-4 of the dataviz reference palette, in fixed order;
    # distinct markers give a second, non-colour encoding.
    style = {
        "binomial_crr": dict(color="#2a78d6", marker="o", label="Binomial (CRR tree), steps"),
        "fd_black_scholes": dict(color="#eb6834", marker="s", label="Finite difference (Douglas), grid"),
        "mc_pseudo_random": dict(color="#1baf7a", marker="^", label="Monte Carlo pseudo-random, samples"),
        "mc_sobol": dict(color="#eda100", marker="D", label="Monte Carlo Sobol (quasi-MC), samples"),
    }
    for engine, kwargs in style.items():
        engine_rows = [r for r in rows if r["engine"] == engine]
        levels = [r["level"] for r in engine_rows]
        errors = [max(r["abs_error"], 1e-6) for r in engine_rows]  # guard log(0)
        ax.plot(levels, errors, linewidth=2, markersize=6, **kwargs)
        if engine == "mc_pseudo_random":
            ax.plot(
                levels,
                [r["std_error"] for r in engine_rows],
                color=kwargs["color"],
                linestyle="--",
                linewidth=1.5,
                label="Monte Carlo pseudo-random: 1 std. error",
            )

    ax.axhline(FINEST_TOL, color="#6b6b6b", linestyle=":", linewidth=1)
    ax.annotate(
        f"finest tolerance {FINEST_TOL}",
        xy=(1, FINEST_TOL),
        xycoords=("axes fraction", "data"),
        xytext=(-4, 3),
        textcoords="offset points",
        ha="right",
        va="bottom",
        fontsize=8,
        color="#4a4a4a",
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Refinement level (tree steps / FD grid size / MC samples)")
    ax.set_ylabel("Absolute error vs analytic price")
    ax.set_title("One European call, four engines: convergence to Black-Scholes")
    # Legend below the axes: inside, it would sit on top of the FD line.
    ax.legend(fontsize=8, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.13), frameon=False)
    ax.grid(True, which="both", linestyle=":", linewidth=0.5, alpha=0.6)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "pricing_convergence.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> dict[str, Any]:
    process = build_process()
    option = build_option()  # the ONE instrument; only engines change below

    analytic_row, rows = run_all_engines(option, process)
    check_single_instrument([analytic_row] + rows, option)
    check_finest_levels(rows)

    repro = article_setup_repro()
    schedule = schedule_demo()
    summary = write_outputs(rows, analytic_row, schedule, article_repro=repro)
    analytic_price = analytic_row["price"]

    print("=" * 78)
    print("quantstack.pricing.four_engines -- one instrument, four engines")
    print("=" * 78)
    print(
        f"QuantLib {ql.__version__}  |  eval {EVAL_DATE.ISO()} -> expiry {maturity_date().ISO()}, "
        f"T={year_fraction():.6f}  |  1 VanillaOption for {len(rows) + 1} rows"
    )
    print(f"Analytic (Black-Scholes-Merton): {analytic_price:.6f}")
    for name in NUMERICAL_ENGINES:
        r = _finest(rows, name)
        se = f"  SE={r['std_error']:.4f}" if r["std_error"] is not None else ""
        print(
            f"{name:>18}: finest level={r['level']:>9}  price={r['price']:.6f}  "
            f"abs_error={r['abs_error']:.6f}{se}  ({r['seconds'] * 1000:.2f} ms)"
        )
    mc = _finest(rows, "mc_pseudo_random")
    print(
        f"  MC pseudo-random checked as abs_error < {MC_SE_MULTIPLE:g}*SE; its {mc['abs_error']:.5f} is "
        f"{mc['abs_error'] / mc['std_error']:.2f} SE (a fixed {FINEST_TOL} would be seed luck)"
    )
    print("-" * 78)
    print(
        f"Article gap: {analytic_price - ARTICLE_REFERENCE['analytic']:+.6f} on analytic.  The article "
        f"used a 366-day life (T=366/365).  Repro at eval {repro['evaluation_date']}:"
    )
    for name, ref in ARTICLE_REFERENCE.items():
        p = repro["prices"][name]
        tag = "4dp match" if repro["matches_article_4dp"][name] else (
            f"{repro['mc_pseudo_random_diff_in_std_errors']:.2f} SE from article" if name == "mc_pseudo_random" else "MISMATCH"
        )
        print(f"{name:>18}: {p['price']:.6f}  (article {ref})  {tag}")
    print("-" * 78)
    print(
        f"Schedule demo: {schedule['count']} dates, {schedule['first_dates']} ... {schedule['last_dates']}"
    )
    print(
        f"  first period day-count fraction: 30/360 BondBasis={schedule['day_count_fraction']['thirty360_bondbasis']:.6f}"
        f"  Actual360={schedule['day_count_fraction']['actual360']:.6f}"
    )
    print("-" * 78)
    print(f"Wrote {RESULTS_DIR / 'pricing_convergence.csv'}")
    print(f"Wrote {RESULTS_DIR / 'pricing_summary.json'}")
    print(f"Wrote {FIGURES_DIR / 'pricing_convergence.png'}")
    return summary


if __name__ == "__main__":
    main()
