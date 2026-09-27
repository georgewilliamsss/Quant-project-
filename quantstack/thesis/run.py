"""Run the thesis book through NautilusTrader several ways and compare them.

``python -m quantstack.thesis.run [--preset thesis5y|broad1y|all54] [--quick] [--no-dashboard]
[--exclude TICKER,TICKER] ...``
(``make thesis``; ``make thesis-quick`` for the 6-name CI smoke run)

The book is the user's own 54-line portfolio (``data/thesis/thesis_holdings.csv``)
priced from their thesis build's GBP total-return panel (``prices_gbp_daily.csv``).
The weighting schemes run on the *same* engine, window, schedule and cash:

* ``own_weights``      -- the thesis's ``weight_total`` column, renormalised over
  the names with usable prices, as fixed weights (``allocator="fixed"``): the
  book is pulled back to them at every rebalance;
* ``own_weights_8020`` -- the same weights renormalised *within* each sleeve, so
  core and moonshot keep the thesis's 80/20 split when names are excluded
  (identical to ``own_weights`` when nothing is excluded);
* ``equal_weight``     -- 1/N over the same names (``allocator="equal"``);
* ``hrp_optimised``    -- the pipeline's own optimiser, skfolio's Hierarchical
  Risk Parity refitted on the trailing ``lookback_bars`` levels at every
  rebalance inside the event loop (``allocator="hrp"``).

Presets (:data:`PRESETS`)
-------------------------
``thesis5y`` (default, primary): 2020-12-10 to 2026-09-16 with a 193-bar
warm-up, so the first fill lands on 2021-09-16 -- the thesis's own base date --
and the run covers the thesis's 5-year window with the 35 names listed by
2020-12-10 (SMGB.L, the largest line, lists that day).  ``broad1y``: every
holding with at least 252 bars (50 names), about one year of trading.
``all54``: the only window in which all 54 names have prices (68 rows), a
plumbing and weight check, not performance evidence.  ``--start``, ``--end``,
``--lookback`` and ``--rebalance-every`` override a preset.  ``--exclude``
drops named holdings for a sensitivity run (recorded as ``excluded_by_user``);
everything else stays as the preset sets it.

Steps (:func:`run_thesis`)
--------------------------
1. Holdings and the price panel are loaded and validated
   (:mod:`~quantstack.thesis.universe`, :mod:`~quantstack.thesis.data`); the
   panel file is checked against the build's manifest (sha256, and the
   canonical shape), then cut to the holding columns in holdings order.
2. Documented level repairs (:mod:`~quantstack.thesis.repairs`: two unadjusted
   MSCL.TO consolidations) are applied to the full series, then the window is
   cut: late listings are excluded with the reason recorded, gaps of at most 3
   bars are forward-filled, longer ones raise.  The thesis weights are
   renormalised over the survivors (the core/moonshot split before and after
   is recorded, and per scheme).
3. Each column is rescaled so its minimum over the window is 100
   (``data.rescale_for_engine``; returns unchanged) -- the panel holds
   total-return index levels from 0.0008 to 26,000, and the engine trades whole
   shares at a 0.01 tick.  The engine trades a GBP 100,000,000 book so that
   whole-share rounding stays under 2% of the smallest line; curves and final
   equity are reported scaled to the GBP 200,000 thesis book.
4. Allocation stage on the window's daily returns: the thesis weights (both
   renormalisations), 1/N, HRP, Max Sharpe (sample covariance; failures are
   recorded, not fatal) and inverse variance, each scored in-sample with
   ``allocation.compare``'s formulas -> ``allocation/``.
5. One ``execution.backtest.run_backtest`` per scheme (with its equal-weight
   benchmarks; ``symbols`` is always the panel's columns and fixed weights
   cover exactly those), written with ``write_results`` and ``plot_equity``
   into ``<results>/<scheme>/`` under the standard ``execution_*`` names, plus
   an ``execution_summary.json`` in the execution module's layout.  A scheme
   that raises is recorded as failed and the others still run.
6. Optionally each run's CSVs are replayed through the dashboard server
   (``python -m quantstack.dashboard.server --replay ... --once``) into
   ``<scheme>/dashboard_summary.json``; failures are recorded, not fatal.
7. ``thesis_summary.json``, ``thesis_comparison.md`` (with the thesis's own
   comparator figures and a Sharpe at its rf = 3.75%), ``thesis_equity.csv``,
   ``data_availability.csv`` and ``figures/thesis_equity.png`` /
   ``figures/thesis_weights.png``.

Currency: every amount is GBP.  The engine's venue books in USD (hard-wired in
``execution``), so the per-scheme files say USD/$ where they mean GBP, in
engine units (the GBP 100,000,000 book); the thesis-level files say GBP and
scale to the GBP 200,000 book.  No FX is applied anywhere: the panel is
already in GBP.

Determinism: nothing is random.  HRP, Max Sharpe (a convex solver), the engine
and the sorting of every output are deterministic, so a rerun reproduces every
number except the runtimes.

Exit status (CLI): 0 every scheme ran; 1 a scheme failed (the summary is still
written); 2 bad inputs (checked before any engine is built).
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from quantstack.thesis.data import (
    DEFAULT_MAX_FFILL_GAP,
    availability,
    engine_price_diagnostics,
    filled_cells,
    load_panel,
    rescale_for_engine,
    select_window,
    verify_panel_file,
)
from quantstack.thesis.repairs import REPAIRS, apply_repairs
from quantstack.thesis.universe import (
    EXPECTED_HOLDINGS,
    SLEEVES,
    load_holdings,
    renormalise,
    renormalise_within_sleeves,
    sleeve_of,
    sleeve_split,
    thesis_weights,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRICES = REPO_ROOT / "prices_gbp_daily.csv"
DEFAULT_HOLDINGS = REPO_ROOT / "data" / "thesis" / "thesis_holdings.csv"
RESULTS_ROOT = REPO_ROOT / "results" / "thesis"
QUICK_RESULTS = REPO_ROOT / "results" / "quick" / "thesis"  # results/quick/ is gitignored
#: ``prices_gbp_daily.csv`` as uploaded: 2016-09-16..2026-09-16, 84 columns.
CANONICAL_SHAPE = (2526, 84)
CURRENCY = "GBP"
#: The thesis book the curves are scaled to.
BOOK_VALUE = 200_000.0
#: The engine's book: large enough that whole shares at levels >= 100 quantise
#: the smallest line (~0.5%) by under 2%.
DEFAULT_CASH = 100_000_000.0
#: The thesis holds 0.376% cash; 1% keeps a rounding buffer for the engine.
DEFAULT_INVESTMENT_CAP = 0.99
#: The thesis's risk-free rate (``analysis_results.json`` config.rf_annual).
THESIS_RF = 0.0375

#: scheme -> the execution engine's allocator
SCHEMES: dict[str, str] = {"own_weights": "fixed", "own_weights_8020": "fixed",
                           "equal_weight": "equal", "hrp_optimised": "hrp"}
ALL_SCHEMES: tuple[str, ...] = tuple(SCHEMES)
BASE_SCHEMES: tuple[str, ...] = ("own_weights", "equal_weight", "hrp_optimised")


@dataclass(frozen=True)
class Preset:
    """A named backtest configuration (window, warm-up, schedule, schemes)."""

    name: str
    start: str
    end: str
    lookback_bars: int
    rebalance_every: int
    schemes: tuple[str, ...]
    label: str
    description: str


PRESETS: dict[str, Preset] = {
    "thesis5y": Preset(
        "thesis5y", "2020-12-10", "2026-09-16", 193, 21, ALL_SCHEMES,
        "the thesis's 5-year window (primary)",
        "Primary configuration. The window starts on 2020-12-10, SMGB.L's first level (the largest line, "
        "13.3% of the book); the 193-bar warm-up puts the first fill on 2021-09-16, the thesis's own base "
        "date, so the run covers the same 5 years as the thesis's realised-daily figures. Names listed "
        "after 2020-12-10 cannot be held for the whole window and are excluded."),
    "broad1y": Preset(
        "broad1y", "2024-09-26", "2026-09-16", 252, 21, ALL_SCHEMES,
        "every name with a year of history (about 1 year of trading)",
        "Secondary configuration: every holding with at least 252 bars by 2026-09-16 (BIOA, the latest "
        "such listing, sets the start), a full 252-bar warm-up and about one year of trading. Too short "
        "for statistical claims."),
    "all54": Preset(
        "all54", "2026-06-12", "2026-09-16", 21, 21, BASE_SCHEMES,
        "all 54 names, plumbing and weight check",
        "The only window in which all 54 holdings have prices (SPCX lists on 2026-06-12): 68 rows, a "
        "21-bar warm-up and 3 rebalances. It checks that every name trades and that the fixed weights "
        "reproduce the thesis's 80/20 split. It is not performance evidence, and HRP on 20 returns of 54 "
        "names is noise by construction."),
}
DEFAULT_PRESET = "thesis5y"

#: ``--quick``: four core and two moonshot lines with full, gap-free history, 400 bars.
QUICK_TICKERS: tuple[str, ...] = ("ISF.L", "SGLN.L", "SHEL.L", "IBTM.L", "GSIT", "BGO.L")
QUICK_BARS = 400

#: The thesis's own headline figures (``analysis_results.json``), for the comparison.
THESIS_COMPARATORS: dict = {
    "window": ("2021-09-16", "2026-09-16"),
    "rf": THESIS_RF,
    "rows": [
        {"series": "Core (Moderate12)", "convention": "realised daily, 5y (1261 obs)", "cagr": 0.2607,
         "ann_vol": 0.1206, "sharpe_rf_thesis": 1.67, "max_drawdown": 0.1338,
         "source": "analysis_results.json portfolios.Moderate12.realised_daily_5y"},
        {"series": "Combined 80/20 book", "convention": "realised daily, 5y", "cagr": 0.2302,
         "ann_vol": 0.1303, "sharpe_rf_thesis": 1.37, "max_drawdown": 0.1685,
         "source": "analysis_results.json combined_portfolio.realised_daily_5y"},
        {"series": "VWRP.L (FTSE All-World)", "convention": "realised daily, 5y", "cagr": 0.1137,
         "ann_vol": 0.1302, "sharpe_rf_thesis": 0.60, "max_drawdown": 0.1764,
         "source": "analysis_results.json asset_stats['VWRP.L']"},
    ],
    "structural_differences": [
        "the engine rebalances every 21 trading days; the thesis's realised-daily figures hold the "
        "weights constant daily (and its monthly backtest rebalances at month-ends);",
        "names listed after the window starts are excluded here (thesis5y: 19 names, 11% of the book, "
        "SPCX and 18 moonshots), so the included book is core-heavier unless own_weights_8020 is used;",
        "the thesis's moonshot figures are equal-weight over all 40 moonshot names, not only the ones "
        "with a full history.",
    ],
}


# --------------------------------------------------------------------------- helpers


def _jsonable(obj, nd: int = 8):
    """JSON-safe copy: non-finite floats -> None, numpy/pandas scalars -> Python, dates -> ISO."""
    if obj is pd.NaT or obj is None:
        return None
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return round(float(obj), nd) if math.isfinite(obj) else None
    if isinstance(obj, pd.Timestamp):
        return obj.date().isoformat()
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, Mapping):
        return {str(k): _jsonable(v, nd) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v, nd) for v in obj]
    return obj


def _write_json(obj, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(obj), indent=2) + "\n")
    return path


def _display_path(path: Path) -> str:
    path = Path(path).resolve()
    return str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)


def _versions() -> dict:
    import nautilus_trader
    import skfolio

    return {"nautilus_trader": nautilus_trader.__version__, "skfolio": skfolio.__version__,
            "pandas": pd.__version__, "numpy": np.__version__, "python": sys.version.split()[0]}


def parse_schemes(spec: str | Sequence[str]) -> tuple[str, ...]:
    """``"own_weights,hrp_optimised"`` (or a sequence) -> validated tuple in the given order."""
    items = [s.strip() for s in (spec.split(",") if isinstance(spec, str) else spec) if s and s.strip()]
    if not items:
        raise ValueError(f"no schemes given; choose from {list(SCHEMES)}")
    bad = [s for s in items if s not in SCHEMES]
    if bad:
        raise ValueError(f"unknown scheme(s) {bad}; choose from {list(SCHEMES)}")
    dups = sorted({s for s in items if items.count(s) > 1})
    if dups:
        raise ValueError(f"duplicate scheme(s) {dups}")
    return tuple(items)


def quick_start(panel: pd.DataFrame, end: str | pd.Timestamp, bars: int = QUICK_BARS) -> str:
    """The date ``bars`` rows before (and including) the last panel row on or before ``end``."""
    idx = panel.loc[: pd.Timestamp(end)].index
    if len(idx) < bars:
        raise ValueError(f"--quick needs {bars} bars up to {pd.Timestamp(end).date()}, the panel has {len(idx)}")
    return idx[-bars].date().isoformat()


def zero_return_share(prices: pd.DataFrame) -> dict[str, float]:
    """Per ticker, the share of days with an exactly unchanged level (stale prints)."""
    r = prices.pct_change().iloc[1:]
    return {str(c): float((r[c] == 0).mean()) for c in r.columns}


def caveats(rescaled: bool, repairs: Sequence[dict], stale: Mapping[str, float],
            included: Sequence[str], starting_cash: float, investment_cap: float) -> list[str]:
    """The comparison's caveats, specific to this run's data and settings."""
    out = [
        "Look-ahead in the own-weights runs: the thesis chose its names and weights on 2026-09-16, with "
        "hindsight over this whole window; backtesting them from the window start flatters them. Treat "
        "those runs as a description of the chosen book, not as evidence the choice would have worked.",
        "Survivorship and composition: only names listed before the window starts are held. own_weights "
        "spreads the excluded names' weight pro rata, which tilts the book towards core; own_weights_8020 "
        "keeps the thesis's sleeve split instead.",
        "Optimistic market-on-close fills: each rebalance is sized on a day's closes and fills at that same "
        "close. No commissions, no stamp duty, no spreads, no FX costs, unlimited liquidity. The thesis "
        "notes phone-dealt names (GBP 49 each way) and spreads that dominate costs for the smallest names; "
        "none of that is modelled.",
        ("Prices are the thesis build's GBP total-return index (dividends reinvested, FX applied), each "
         "column rescaled so its window minimum is 100; returns are unchanged (see Data)."
         if rescaled else
         "Prices are the thesis build's GBP total-return index levels, passed unrescaled (--no-rescale): "
         "levels far below 1 lose precision to the tick and levels in the thousands buy few whole shares."),
        f"The engine trades a GBP {starting_cash:,.0f} book in whole shares with {investment_cap:.0%} of "
        f"equity deployed ({1 - investment_cap:.1%} cash; the thesis holds 0.376%); curves are scaled to "
        f"the GBP {BOOK_VALUE:,.0f} book, so they show none of the thesis's own whole-share rounding.",
    ]
    applied = [r for r in repairs if r.get("applied") and r["ticker"] in included]
    if applied:
        out.append("Repaired levels: " + "; ".join(f"{r['ticker']} before {r['date']} divided by "
                                                   f"{r['factor']:.4g} ({r['verified']})" for r in applied)
                   + ". Other large one-day moves in the panel are the thesis build's and are not verified here.")
    flagged = {t: s for t, s in stale.items() if s > 0.2}
    if flagged:
        out.append("Stale prints (share of days with an unchanged level): "
                   + ", ".join(f"{t} {s:.0%}" for t, s in flagged.items())
                   + ". Stale prints understate a name's volatility, so HRP overweights it.")
    if "DBMG.L" in included:
        out.append("DBMG.L's history before April 2025 is its proxy (DBMF) in the thesis build.")
    out += [
        "The allocation-stage statistics are in-sample: HRP and Max Sharpe are fitted on the returns they "
        "are scored on. The backtests are not: the engine's HRP only ever sees the trailing lookback window.",
        "The engine books in USD; per-scheme files label GBP amounts as USD/$, in engine units.",
    ]
    return out


# --------------------------------------------------------------------------- allocation stage


def allocation_stage(returns: pd.DataFrame, thesis_raw: Mapping[str, float],
                     targets: Mapping[str, Mapping[str, float] | None],
                     sleeves: Mapping[str, str]) -> tuple[pd.DataFrame, dict]:
    """Every weight vector on the window's daily returns, plus in-sample stats.

    ``targets`` holds the precomputed vectors, ``thesis_w_renormalised`` and
    ``thesis_w_8020`` (``None`` when it cannot be formed).  Returns
    ``(weights_table, summary)``: one row per ticker, columns ``ticker,
    sleeve, thesis_w, thesis_w_renormalised, thesis_w_8020, equal_w, hrp_w,
    max_sharpe_w, inv_var_w``.  A fitter that raises leaves its column NaN and
    its message in ``summary["errors"]``.  Max Sharpe on the sample covariance
    of 35-50 names is the fragile one (the solver can fail, or the answer can
    be a handful of names); it is recorded, never fatal.
    """
    from quantstack.allocation.weights import (
        build_max_sharpe,
        equal_weight,
        hrp_weights,
        inverse_variance_weights,
    )
    from quantstack.contracts import fit_weights
    from quantstack.thesis.report import in_sample_stats

    fitters = {
        "equal_w": equal_weight,
        "hrp_w": hrp_weights,
        "max_sharpe_w": lambda r: fit_weights(build_max_sharpe(), r),
        "inv_var_w": inverse_variance_weights,
    }
    tickers = list(returns.columns)
    vectors: dict[str, dict[str, float]] = {k: dict(v) for k, v in targets.items() if v is not None}
    errors: dict[str, str] = {k: "not formed (a sleeve has no included name)" for k, v in targets.items()
                              if v is None}
    seconds: dict[str, float] = {}
    for key, fit in fitters.items():
        t0 = time.perf_counter()
        try:
            vectors[key] = {str(k): float(v) for k, v in fit(returns).items()}
        except Exception as exc:  # noqa: BLE001 -- any optimiser failure is data, not a crash
            errors[key] = f"{type(exc).__name__}: {exc}"
        seconds[key] = time.perf_counter() - t0
    table = pd.DataFrame({"ticker": tickers, "sleeve": [sleeves[t] for t in tickers],
                          "thesis_w": [float(thesis_raw[t]) for t in tickers]})
    for key in (*targets, *fitters):
        table[key] = [vectors[key][t] if key in vectors else float("nan") for t in tickers]
    stats = {}
    for key, w in vectors.items():
        try:
            stats[key] = in_sample_stats(returns, w)
        except ValueError as exc:  # e.g. a solver that returned a partly invested vector
            errors.setdefault(key, f"in-sample stats: {exc}")
    summary = {
        "window": {"first_return": returns.index[0], "last_return": returns.index[-1],
                   "n_days": int(len(returns))},
        "n_assets": len(tickers),
        "method": "each vector held constant over the window, rebalanced daily, no costs; "
                  "formulas of quantstack.allocation.compare (sharpe = mean/std(ddof=1)*sqrt(252), "
                  "annualized_mean_arithmetic = mean*252, cagr/max_drawdown_compounded on "
                  "compounded wealth)",
        "fitted_on": "the whole window's daily returns (in-sample)",
        "stats": stats,
        "errors": errors,
        "fit_seconds": seconds,
    }
    return table, summary


# --------------------------------------------------------------------------- one scheme


@dataclass(frozen=True)
class EngineConfig:
    lookback_bars: int
    rebalance_every: int
    starting_cash: float
    investment_cap: float
    log_level: str
    equity_scale: float


def scheme_metrics(res: dict, scale: float) -> dict:
    """The per-scheme numbers ``thesis_summary.json`` compares (equity also scaled to the book)."""
    from quantstack.thesis.report import sharpe_rf

    m, st = res["metrics"], res["stats"]
    held = {p.symbol for p in (res["snapshot"].positions if res["snapshot"] else [])}
    universe = list(res["prices"].columns)
    return {
        **{k: m.get(k) for k in ("cagr", "ann_vol", "sharpe", "max_drawdown", "max_drawdown_peak",
                                 "max_drawdown_trough", "total_return", "final_equity", "start_equity",
                                 "turnover_annual_oneway", "turnover_annual_oneway_ex_initial")},
        "final_equity_book": m["final_equity"] * scale, "start_equity_book": m["start_equity"] * scale,
        "sharpe_rf_thesis": sharpe_rf(m.get("cagr"), m.get("ann_vol"), THESIS_RF),
        "fills": st["n_fills"], "orders": st["n_orders"], "denied": st["n_denied"],
        "rejections": st["n_rejected"], "first_fill_date": st["first_fill_date"],
        "n_rebalances": st["n_rebalances"], "halted_early": st["halted_early"],
        "n_names": len(universe), "n_names_held_at_end": len(held),
        "names_not_held_at_end": [s for s in universe if s not in held],
        "engine_run_seconds": st["engine_run_seconds"],
    }


def _benchmark_metrics(metrics: Mapping, scale: float, **extra) -> dict:
    from quantstack.thesis.report import sharpe_rf

    return {**metrics, **extra, "final_equity_book": metrics["final_equity"] * scale,
            "sharpe_rf_thesis": sharpe_rf(metrics.get("cagr"), metrics.get("ann_vol"), THESIS_RF)}


def _public(stats: Mapping) -> dict:
    return {k: v for k, v in stats.items() if k not in ("weights_history", "achieved_weights_history", "submitted")}


def _execution_summary(scheme: str, res: dict, cfg: EngineConfig, fixed: Mapping[str, float] | None,
                       paths: Mapping[str, Path], prices_path: Path) -> dict:
    """``<scheme>/execution_summary.json`` in the execution module's layout (the keys it shares)."""
    from quantstack.execution.backtest import FILL_ASSUMPTION

    alloc = SCHEMES[scheme]
    ee, ep = res["equal_engine"], res["equal_pandas"]
    return {
        "module": "thesis",
        "scheme": scheme,
        "universe": list(res["prices"].columns),
        "window": {"first_bar": res["prices"].index[0], "last_bar": res["prices"].index[-1],
                   "trading_days": int(len(res["prices"]))},
        "data_source": f"{_display_path(prices_path)} (GBP total return; engine_prices in thesis_summary.json "
                       "says how it was rescaled)",
        "config": {"starting_cash": cfg.starting_cash, "currency": CURRENCY, "engine_currency_label": "USD",
                   "equity_scale_to_thesis_book": cfg.equity_scale, "lookback_bars": cfg.lookback_bars,
                   "rebalance_every": cfg.rebalance_every, "investment_cap": cfg.investment_cap,
                   "allocator": alloc, "order_mode": "two_phase", "oms": "NETTING", "account": "CASH",
                   "fill_model": "default", "fees": "none",
                   **({"fixed_weights_normalised": dict(fixed)} if fixed is not None else {})},
        "fills": res["stats"]["n_fills"],
        "orders": res["stats"]["n_orders"],
        "rejections": res["stats"]["n_rejected"],
        "denied": res["stats"]["n_denied"],
        "first_fill_date": res["stats"]["first_fill_date"],
        alloc: {"metrics": res["metrics"], "stats": _public(res["stats"])},
        "equal_engine": {"metrics": ee["metrics"], "stats": _public(ee["stats"])} if ee else None,
        "equal_pandas": ({"metrics": ep["metrics"], "daily_rebalanced_metrics": ep["daily_rebalanced_metrics"],
                          "definition": "starting_cash * (prices.loc[first_fill:] / "
                                        "prices.loc[first_fill]).mean(axis=1)"}
                         if ep else None),
        "runtime_seconds": {"backtest_with_benchmarks": res["runtime_seconds"],
                            f"{alloc}_engine_run": res["stats"]["engine_run_seconds"]},
        "outputs": {k: _display_path(v) for k, v in paths.items()},
        "notes": {"fill_assumption": FILL_ASSUMPTION,
                  "currency": "amounts are GBP in engine units (the starting cash above); the engine's venue "
                              "books in USD, so files label them USD/$"},
    }


def fixed_weights_for(prices: pd.DataFrame, target: Mapping[str, float]) -> dict[str, float]:
    """``target`` restricted to exactly the panel's columns; ``ValueError`` unless the two sets agree.

    ``run_backtest`` requires the fixed-weight keys to be the universe, no
    more and no fewer; checking here names the offending tickers before an
    engine is built.
    """
    cols = [str(c) for c in prices.columns]
    missing, extra = sorted(set(cols) - set(target)), sorted(set(target) - set(cols))
    if missing or extra:
        raise ValueError(f"fixed weights and price columns disagree: no weight for {missing}, "
                         f"weights without prices for {extra}")
    return {c: float(target[c]) for c in cols}


def run_scheme(scheme: str, prices: pd.DataFrame, target: Mapping[str, float] | None, cfg: EngineConfig,
               out_dir: Path, prices_path: Path) -> dict:
    """Backtest one scheme and write ``out_dir``; return the ``run_backtest`` result dict.

    ``symbols`` is always ``list(prices.columns)``; a fixed-weight scheme's
    ``target`` must cover exactly those columns (:func:`fixed_weights_for`).
    """
    from quantstack.execution.backtest import plot_equity, run_backtest, write_results

    alloc = SCHEMES[scheme]
    if alloc == "fixed" and target is None:
        raise ValueError(f"{scheme} needs target weights")
    fixed = fixed_weights_for(prices, target) if alloc == "fixed" else None
    res = run_backtest(symbols=list(prices.columns), start=prices.index[0].date().isoformat(),
                       end=prices.index[-1].date().isoformat(), allocator=alloc,
                       starting_cash=cfg.starting_cash, lookback_bars=cfg.lookback_bars,
                       rebalance_every=cfg.rebalance_every, investment_cap=cfg.investment_cap,
                       benchmarks=True, prices=prices, log_level=cfg.log_level, fixed_weights=fixed)
    st = res["stats"]
    if res["first_fill"] is None:
        raise RuntimeError(f"{scheme}: the backtest produced no fills (orders {st['n_orders']}, denied "
                           f"{st['n_denied']}, rejected {st['n_rejected']}); nothing written")
    if st["halted_early"]:
        raise RuntimeError(f"{scheme}: the engine stopped early on {st['last_published_day']}: "
                           f"{st['rejections_sample']}")
    paths = write_results(res, out_dir)
    paths["figure"] = plot_equity(res["curves"], res["first_fill"], out_dir / "figures" / "execution_equity.png",
                                  title_extra=f", thesis book ({prices.shape[1]} names)",
                                  currency="£", scale=cfg.equity_scale)
    paths["summary"] = out_dir / "execution_summary.json"
    _write_json(_execution_summary(scheme, res, cfg, fixed, paths, prices_path), paths["summary"])
    return res


def tracking_summary(wt: Mapping | None, achieved_csv: str | None = None, top: int = 5) -> dict | None:
    """The engine's ``stats["weight_tracking"]`` boiled down for the comparison.

    ``None`` when the engine did not report it.  Gaps compare the achieved
    weight (right after each rebalance's fills) with ``investment_cap x
    target``, as ``execution.backtest.weight_tracking`` defines them.  Adds
    the names held at under half their capped target on average and the
    ``top`` names by mean absolute gap.
    """
    if not wt or not wt.get("n_rebalances"):
        return None
    per = wt.get("per_symbol") or {}
    ranked = sorted(per.items(), key=lambda kv: (-kv[1]["mean_abs_gap"], kv[0]))
    return {
        "achieved_csv": achieved_csv, "basis": wt.get("basis"), "n_rebalances": wt["n_rebalances"],
        "mean_abs_gap": wt["mean_abs_gap"], "max_abs_gap": wt["max_abs_gap"],
        "max_abs_gap_symbol": wt.get("max_abs_gap_symbol"), "max_abs_gap_date": wt.get("max_abs_gap_date"),
        "mean_invested_fraction": wt.get("mean_invested_fraction"),
        "names_below_half_target": [t for t, v in per.items() if v["mean_capped_target"] > 0
                                    and v["mean_achieved"] < 0.5 * v["mean_capped_target"]],
        "largest_gaps": [{"ticker": t, **v} for t, v in ranked[:top]],
    }


def whole_unit_check(prices: pd.DataFrame, lookback_bars: int, starting_cash: float, investment_cap: float,
                     targets: Mapping[str, Mapping[str, float]]) -> dict:
    """Whole shares each static target buys at the first rebalance's levels.

    The first rebalance is bar ``lookback_bars`` (the strategy's warm-up), at
    ``starting_cash * investment_cap`` deployable; shares are floored exactly
    as ``contracts.target_deltas`` does.  ``targets`` maps a scheme to its
    weights (the fixed and equal schemes: HRP's change at every rebalance).
    Returns the date, and per scheme the names that get no share and those
    that get fewer than 3 (where one share is a third or more of the target).
    """
    row = prices.iloc[lookback_bars - 1]
    deploy = starting_cash * investment_cap
    out: dict = {"date": prices.index[lookback_bars - 1], "deployable": deploy, "schemes": {}}
    for scheme, w in targets.items():
        units = {t: int(deploy * float(w[t]) // float(row[t])) for t in prices.columns}
        out["schemes"][scheme] = {
            "zero_units": [{"ticker": t, "target_value": deploy * float(w[t]), "price": float(row[t])}
                           for t in prices.columns if units[t] == 0],
            "under_3_units": [t for t in prices.columns if 0 < units[t] < 3],
        }
    return out


def replay_dashboard(scheme_dir: Path, timeout: float = 300.0) -> dict:
    """Replay one run's CSVs through ``python -m quantstack.dashboard.server --once``.

    Writes ``scheme_dir/dashboard_summary.json``; returns what happened.  Never
    raises: a failure (non-zero exit, timeout, demo-data fallback) comes back
    as ``{"status": "failed", "error": ...}``.
    """
    out = scheme_dir / "dashboard_summary.json"
    cmd = [sys.executable, "-m", "quantstack.dashboard.server",
           "--replay", str(scheme_dir / "execution_equity.csv"), str(scheme_dir / "execution_positions.csv"),
           "--fills", str(scheme_dir / "execution_fills.csv"), "--once", "--summary", str(out)]
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(REPO_ROOT))
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    rec: dict = {"seconds": time.perf_counter() - t0, "returncode": proc.returncode}
    if proc.returncode != 0 or not out.is_file():
        return {**rec, "status": "failed",
                "error": f"exit {proc.returncode}: {(proc.stderr or proc.stdout).strip()[-800:]}"}
    try:
        s = json.loads(out.read_text())
        replay, wire = s["replay"], s.get("wire_selftest") or {}
    except (ValueError, KeyError) as exc:
        return {**rec, "status": "failed", "error": f"unreadable {out.name}: {exc}"}
    ok = not replay["is_demo"]
    return {**rec, "status": "ok" if ok else "failed",
            "error": None if ok else f"fell back to demo data: {replay.get('fallback_reason')}",
            "summary_file": _display_path(out),
            "table_sizes_after_load": replay.get("table_sizes_after_load"),
            "equity_source_column": replay.get("equity_source_column"),
            "selftest_origin_policy_enforced": wire.get("origin_policy_enforced"),
            "selftest_float_round_trip_bit_exact": wire.get("float_round_trip_bit_exact")}


# --------------------------------------------------------------------------- the run


def _weights_frame(history: list[dict], tickers: Sequence[str]) -> pd.DataFrame:
    return pd.DataFrame(history).drop(columns="date").reindex(columns=list(tickers)).astype(float)


def _intended_split(scheme: str, res: dict, targets: Mapping[str, Mapping[str, float] | None],
                    sleeves: Mapping[str, str], included: Sequence[str]) -> tuple[dict, str]:
    """(sleeve split the scheme aims for, how it was measured)."""
    if scheme == "own_weights":
        return sleeve_split(targets["own_weights"], sleeves), "thesis weights renormalised over included names"
    if scheme == "own_weights_8020":
        return sleeve_split(targets["own_weights_8020"], sleeves), "thesis split kept, renormalised within sleeves"
    if scheme == "equal_weight":
        return {s: sum(sleeves[t] == s for t in included) / len(included) for s in SLEEVES}, "1/N name counts"
    w = _weights_frame(res["stats"]["weights_history"], included).mean()
    return sleeve_split(w.to_dict(), sleeves), "HRP targets, mean over rebalances"


def _exclusion_records(exclusions: pd.DataFrame, sleeves: Mapping[str, str]) -> list[dict]:
    recs = []
    for r in exclusions.to_dict("records"):
        recs.append({**r, "sleeve": sleeves.get(r["ticker"]),
                     "first_valid": None if pd.isna(r["first_valid"]) else pd.Timestamp(r["first_valid"]).date(),
                     "last_valid": None if pd.isna(r["last_valid"]) else pd.Timestamp(r["last_valid"]).date()})
    return recs


def _availability_table(panel: pd.DataFrame, universe: Sequence[str], sleeves: Mapping[str, str],
                        weights: Mapping[str, float], exclusions: pd.DataFrame) -> pd.DataFrame:
    a = availability(panel, universe)
    reasons = dict(zip(exclusions["ticker"], exclusions["reason"]))
    a.insert(0, "sleeve", [sleeves[t] for t in a.index])
    a.insert(1, "weight_total", [weights[t] for t in a.index])
    a["included"] = [t not in reasons for t in a.index]
    a["exclusion_reason"] = [reasons.get(t, "") for t in a.index]
    return a


def run_thesis(
    prices_path: str | Path = DEFAULT_PRICES,
    holdings_path: str | Path = DEFAULT_HOLDINGS,
    results_dir: str | Path = RESULTS_ROOT / DEFAULT_PRESET,
    start: str = PRESETS[DEFAULT_PRESET].start,
    end: str = PRESETS[DEFAULT_PRESET].end,
    lookback_bars: int = PRESETS[DEFAULT_PRESET].lookback_bars,
    rebalance_every: int = PRESETS[DEFAULT_PRESET].rebalance_every,
    starting_cash: float = DEFAULT_CASH,
    investment_cap: float = DEFAULT_INVESTMENT_CAP,
    max_ffill_gap: int = DEFAULT_MAX_FFILL_GAP,
    schemes: Sequence[str] = PRESETS[DEFAULT_PRESET].schemes,
    dashboard: bool = True,
    log_level: str = "WARNING",
    *,
    tickers: Sequence[str] | None = None,
    exclude: Sequence[str] = (),
    strict_calendar: bool = False,
    expected_holdings: int | None = EXPECTED_HOLDINGS,
    rescale: bool = True,
    repairs: bool = True,
    preset: str | None = None,
    book_value: float = BOOK_VALUE,
) -> dict:
    """Run the thesis book under ``schemes`` and write the comparison; return the summary dict.

    ``tickers`` restricts the universe to a subset of the holdings (``--quick``).
    ``exclude`` drops holdings for a sensitivity run (``--exclude``): they stay
    in the universe and are recorded in ``summary["exclusions"]`` with the
    reason ``excluded_by_user``.
    ``rescale`` (min-at-100 per column) and ``repairs`` (:data:`repairs.REPAIRS`)
    are on by default.  ``preset`` names the :data:`PRESETS` entry this run
    stands for (labels only; the window arguments are what runs).  Equity is
    reported scaled by ``book_value / starting_cash``.

    ``ValueError`` for bad inputs, raised before any engine is built: holdings
    or panel that fail validation (including a manifest checksum mismatch),
    a holding missing from the panel, unknown schemes, a gap longer than
    ``max_ffill_gap``, a window with fewer than three usable names or too short
    to trade, or ``own_weights_8020`` with a sleeve that has no included name.
    A scheme that fails inside the engine is recorded
    (``summary["schemes"][scheme]["status"] == "failed"``) and the rest still
    run; ``summary["status"]`` is then ``"failed"``.
    """
    from quantstack.thesis.report import comparison_markdown, plot_thesis_equity, plot_thesis_weights

    t_all = time.perf_counter()
    schemes = parse_schemes(schemes)
    if lookback_bars < 3 or rebalance_every < 1:
        raise ValueError(f"lookback_bars must be >= 3 and rebalance_every >= 1, "
                         f"got {lookback_bars}, {rebalance_every}")
    if not starting_cash > 0 or not 0 < investment_cap <= 1 or not book_value > 0:
        raise ValueError(f"need starting_cash > 0, book_value > 0 and 0 < investment_cap <= 1, got "
                         f"{starting_cash}, {book_value}, {investment_cap}")
    if preset is not None and preset not in PRESETS:
        raise ValueError(f"unknown preset {preset!r}; choose from {list(PRESETS)}")
    prices_path, holdings_path, results = Path(prices_path), Path(holdings_path), Path(results_dir)
    scale = book_value / starting_cash

    # ---- 1. universe and panel
    holdings = load_holdings(holdings_path, expected_n=expected_holdings)
    weights_all, sleeves = thesis_weights(holdings), sleeve_of(holdings)
    universe = list(holdings["ticker"])
    if tickers is not None:
        unknown = [t for t in tickers if t not in weights_all]
        if unknown:
            raise ValueError(f"tickers not in {holdings_path.name}: {unknown}")
        universe = [t for t in universe if t in set(tickers)]
    exclude = list(dict.fromkeys(exclude))
    unknown = [t for t in exclude if t not in weights_all]
    if unknown:
        raise ValueError(f"exclude: tickers not in {holdings_path.name}: {unknown}")
    full = load_panel(prices_path)
    canonical = prices_path.resolve() == DEFAULT_PRICES.resolve()
    panel_check = verify_panel_file(prices_path, full, CANONICAL_SHAPE if canonical else None)
    missing = [t for t in universe if t not in full.columns]
    if missing:
        raise ValueError(f"holdings missing from {prices_path.name}: {missing}")
    panel = full[universe]  # holding columns only, in holdings order
    repair_log: list[dict] = []
    if repairs:
        panel, repair_log = apply_repairs(panel, REPAIRS)

    # ---- 2. window, weights
    raw, exclusions = select_window(panel, universe, start, end, lookback_bars, max_ffill_gap,
                                    strict_calendar=strict_calendar, weights=weights_all, exclude=exclude)
    included = list(raw.columns)
    rescale_check = None
    if rescale:
        prices, factors, rescale_check = rescale_for_engine(raw)
    else:
        prices, factors = raw, None
    universe_w = {t: weights_all[t] for t in universe}
    # the book's own split (80/20 in the thesis), over all holdings even when --quick runs a subset
    thesis_split = sleeve_split(renormalise(weights_all, list(weights_all)), sleeves)
    own = renormalise(weights_all, included)
    try:
        own8020 = renormalise_within_sleeves(weights_all, included, sleeves, thesis_split)
    except ValueError:
        if "own_weights_8020" in schemes:
            raise
        own8020 = None
    targets = {"own_weights": own, "own_weights_8020": own8020}
    split = {"thesis": thesis_split, "before": sleeve_split(universe_w, sleeves),
             "before_normalised": sleeve_split(renormalise(universe_w, universe), sleeves),
             "after": sleeve_split(own, sleeves)}
    filled = filled_cells(panel, raw)
    stale = zero_return_share(raw)
    static = {s: (targets[s] if SCHEMES[s] == "fixed" else dict.fromkeys(included, 1.0 / len(included)))
              for s in schemes if SCHEMES[s] in ("fixed", "equal")}
    units = whole_unit_check(prices, lookback_bars, starting_cash, investment_cap, static)

    results.mkdir(parents=True, exist_ok=True)
    avail = _availability_table(panel, universe, sleeves, weights_all, exclusions)
    avail.to_csv(results / "data_availability.csv", float_format="%.6g", date_format="%Y-%m-%d")

    # ---- 3. allocation stage (on the unrescaled returns of the window: identical to 1e-12)
    returns = raw.pct_change().iloc[1:]
    alloc_table, alloc_summary = allocation_stage(
        returns, {t: weights_all[t] for t in included},
        {"thesis_w_renormalised": own, "thesis_w_8020": own8020}, sleeves)
    alloc_dir = results / "allocation"
    alloc_dir.mkdir(parents=True, exist_ok=True)
    alloc_table.to_csv(alloc_dir / "thesis_allocation_weights.csv", index=False, float_format="%.8f")
    _write_json(alloc_summary, alloc_dir / "thesis_allocation_summary.json")

    # ---- 4. the backtests
    cfg = EngineConfig(lookback_bars, rebalance_every, float(starting_cash), float(investment_cap), log_level,
                       scale)
    runs: dict[str, dict] = {}
    scheme_records: dict[str, dict] = {}
    for scheme in schemes:
        t0 = time.perf_counter()
        try:
            res = run_scheme(scheme, prices, targets.get(scheme), cfg, results / scheme, prices_path)
        except Exception as exc:  # noqa: BLE001 -- record, keep the other schemes
            scheme_records[scheme] = {"status": "failed", "allocator": SCHEMES[scheme],
                                      "error": f"{type(exc).__name__}: {exc}",
                                      "seconds": time.perf_counter() - t0}
            print(f"[thesis] {scheme} FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        runs[scheme] = res
        alloc_name = SCHEMES[scheme]
        achieved_csv = results / scheme / f"execution_weights_{alloc_name}_achieved.csv"
        tracking = tracking_summary(res["stats"].get("weight_tracking"),
                                    f"{scheme}/{achieved_csv.name}" if achieved_csv.is_file() else None)
        intended, basis = _intended_split(scheme, res, targets, sleeves, included)
        scheme_records[scheme] = {"status": "ok", "allocator": alloc_name, **scheme_metrics(res, scale),
                                  "intended_sleeve_split": intended, "intended_sleeve_split_basis": basis,
                                  "target_vs_achieved": tracking,
                                  "results_dir": _display_path(results / scheme),
                                  "seconds": time.perf_counter() - t0}
        m = res["metrics"]
        print(f"[thesis] {scheme:<17} final {CURRENCY} {m['final_equity'] * scale:>10,.0f}  CAGR {m['cagr']:7.2%}  "
              f"vol {m['ann_vol']:6.2%}  Sharpe {m['sharpe']:5.2f}  maxDD {m['max_drawdown']:6.2%}  "
              f"fills {res['stats']['n_fills']}  ({time.perf_counter() - t0:.1f} s)")

    # ---- 5. dashboard replays
    dash: dict[str, dict] = {}
    if dashboard:
        for scheme in runs:
            dash[scheme] = replay_dashboard(results / scheme)

    # ---- 6. aligned equity, benchmarks, figures
    outputs: dict[str, Path] = {"availability_csv": results / "data_availability.csv",
                                "allocation_weights_csv": alloc_dir / "thesis_allocation_weights.csv",
                                "allocation_summary": alloc_dir / "thesis_allocation_summary.json"}
    bench, checks, first_fill = {}, {}, None
    weights_for_report: dict[str, dict[str, float]] = {}
    if runs:
        from quantstack.contracts import write_equity_csv

        engine_curves = pd.concat({f"equity_{s}": r["equity"] for s, r in runs.items()}, axis=1).sort_index()
        book_curves = engine_curves * scale
        both = pd.concat([book_curves, engine_curves.add_suffix("_engine")], axis=1)
        both.index.name = "date"
        outputs["equity_csv"] = write_equity_csv(both.round(2), results / "thesis_equity.csv")
        first = next(iter(runs.values()))
        first_fill = min(r["first_fill"] for r in runs.values())
        ee = first["equal_engine"]
        bench = {"equal_engine": _benchmark_metrics(
                     ee["metrics"], scale, fills=ee["stats"]["n_fills"], denied=ee["stats"]["n_denied"],
                     rejections=ee["stats"]["n_rejected"], first_fill_date=ee["stats"]["first_fill_date"]),
                 "equal_pandas": _benchmark_metrics(first["equal_pandas"]["metrics"], scale, never_trades=True)}
        ee_final = {s: r["equal_engine"]["metrics"]["final_equity"] for s, r in runs.items()}
        checks = {"equal_engine_benchmark_final_equity": ee_final,
                  "equal_engine_benchmark_consistent": len({round(v, 2) for v in ee_final.values()}) == 1}
        panels = {}
        for s, r in runs.items():
            if SCHEMES[s] == "hrp":
                w = _weights_frame(r["stats"]["weights_history"], included)
                weights_for_report[s] = w.mean().to_dict()
                panels[s] = {"weights": w.mean(), "low": w.min(), "high": w.max(),
                             "label": f"HRP: mean of {len(w)} rebalances (bar: min-max)"}
            else:
                weights_for_report[s] = (dict(targets[s]) if SCHEMES[s] == "fixed"
                                         else dict.fromkeys(included, 1.0 / len(included)))
                panels[s] = {"weights": pd.Series(weights_for_report[s]),
                             "label": {"own_weights": "Own (thesis), renormalised",
                                       "own_weights_8020": "Own, 80/20 sleeves (hatched)",
                                       "equal_weight": "Equal weight (1/N)"}[s]}
        outputs["equity_figure"] = plot_thesis_equity(
            book_curves, first_fill, results / "figures" / "thesis_equity.png", symbol="£",
            title=f"Thesis book in NautilusTrader: {len(included)} names, equity from first fill "
                  f"(GBP {book_value:,.0f} book)")
        order = sorted(included, key=lambda t: (sleeves[t] != "core", -weights_all[t], t))
        outputs["weights_figure"] = plot_thesis_weights(panels, order, sleeves,
                                                        results / "figures" / "thesis_weights.png")

    # ---- 7. summary + markdown
    ok = all(r["status"] == "ok" for r in scheme_records.values())
    last_bar = raw.index[-1]
    p = PRESETS.get(preset) if preset else None
    summary = {
        "module": "thesis",
        "status": "ok" if ok else "failed",
        "generated_by": "quantstack.thesis.run",
        "preset": ({**asdict(p), "matches_preset": (start, end, lookback_bars, rebalance_every) ==
                    (p.start, p.end, p.lookback_bars, p.rebalance_every)} if p else None),
        "versions": _versions(),
        "inputs": {"prices": _display_path(prices_path), "holdings": _display_path(holdings_path)},
        "panel_check": panel_check,
        "config": {"start": start, "end": end, "lookback_bars": lookback_bars, "rebalance_every": rebalance_every,
                   "starting_cash": float(starting_cash), "currency": CURRENCY, "book_value": float(book_value),
                   "equity_scale": scale, "investment_cap": investment_cap, "thesis_rf": THESIS_RF,
                   "max_ffill_gap": max_ffill_gap, "strict_calendar": strict_calendar, "rescale": rescale,
                   "repairs": repairs, "schemes": list(schemes),
                   "scheme_allocators": {s: SCHEMES[s] for s in schemes}, "dashboard": dashboard,
                   "tickers_subset": list(tickers) if tickers is not None else None,
                   "exclude": exclude},
        "window": {"start": start, "end": end, "first_bar": raw.index[0], "last_bar": last_bar,
                   "trading_days": int(len(raw)), "first_fill_date": first_fill,
                   "traded_days": int((raw.index >= first_fill).sum()) if first_fill is not None else 0,
                   "traded_years": (last_bar - first_fill).days / 365.25 if first_fill is not None else 0.0},
        "universe": {
            "n_universe": len(universe), "n_included": len(included), "n_excluded": len(exclusions),
            "included": included, "excluded": list(exclusions["ticker"]),
            "excluded_weight_total": float(exclusions["weight_total"].sum()) if len(exclusions) else 0.0,
            "sleeve_split": split,
            "sleeve_counts": {s: sum(sleeves[t] == s for t in included) for s in SLEEVES},
            "n_filled_cells": int(sum(filled.values())),
            "filled_cells": {t: n for t, n in filled.items() if n},
            "own_weights_renormalised": own,
            "own_weights_8020": own8020,
        },
        "exclusions": _exclusion_records(exclusions, sleeves),
        "repairs": repair_log,
        "engine_prices": {
            "rescaled": rescale,
            "method": ("each column x (100 / its minimum over the window), rounded to 6 decimals" if rescale
                       else "raw GBP total-return levels from the panel (not rescaled)"),
            "factors": factors.to_dict() if factors is not None else None,
            "rescale_check": rescale_check,
            "diagnostics": engine_price_diagnostics(prices).to_dict("index"),
            "diagnostics_note": "range_ratio = max/min level in the window; engine_min/engine_max = the levels "
                                "the engine trades at (its tick comes from each instrument's own data)"},
        "data_flags": {"zero_return_share": stale},
        "whole_unit_check": units,
        "schemes": scheme_records,
        "benchmarks": bench,
        "checks": checks,
        "thesis_comparators": THESIS_COMPARATORS,
        "allocation": alloc_summary,
        "weights_for_report": weights_for_report,
        "dashboard": dash,
        "caveats": caveats(rescale, repair_log, stale, included, starting_cash, investment_cap),
        "outputs": {},
        "runtime_seconds": None,
    }
    outputs["comparison_md"] = results / "thesis_comparison.md"
    outputs["summary"] = results / "thesis_summary.json"
    summary["outputs"] = {k: _display_path(v) for k, v in outputs.items()}
    summary["runtime_seconds"] = {"total": time.perf_counter() - t_all,
                                  **{s: r["seconds"] for s, r in scheme_records.items()},
                                  "dashboard": sum(d.get("seconds", 0.0) for d in dash.values())}
    outputs["comparison_md"].write_text(comparison_markdown(_jsonable(summary)))
    _write_json(summary, outputs["summary"])
    return _jsonable(summary)


# --------------------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m quantstack.thesis.run",
        description="Run the thesis portfolio through NautilusTrader under its own weights, its weights with "
                    "the 80/20 sleeve split kept, equal weight and HRP, and write a side-by-side comparison.")
    ap.add_argument("--preset", default=DEFAULT_PRESET, choices=list(PRESETS),
                    help=f"window, warm-up and schemes (default {DEFAULT_PRESET}): "
                         + "; ".join(f"{p.name}: {p.start}..{p.end}, lookback {p.lookback_bars}"
                                     for p in PRESETS.values()))
    ap.add_argument("--prices", default=str(DEFAULT_PRICES),
                    help=f"GBP total-return daily panel (default: {_display_path(DEFAULT_PRICES)})")
    ap.add_argument("--holdings", default=str(DEFAULT_HOLDINGS),
                    help=f"holdings CSV (default: {_display_path(DEFAULT_HOLDINGS)})")
    ap.add_argument("--results", default=None,
                    help=f"output directory (default: {_display_path(RESULTS_ROOT)}/<preset>, or "
                         "<preset>_ex_<tickers> with --exclude; with --quick "
                         f"{_display_path(QUICK_RESULTS)}, which is gitignored)")
    ap.add_argument("--start", default=None, help="first bar of the window (default: the preset's; with --quick, "
                    f"{QUICK_BARS} bars before --end); the first --lookback bars are warm-up")
    ap.add_argument("--end", default=None, help="last bar of the window (default: the preset's)")
    ap.add_argument("--lookback", type=int, default=None, help="warm-up and HRP window in bars (default: the preset's)")
    ap.add_argument("--rebalance-every", type=int, default=None,
                    help="trading days between rebalances (default: the preset's)")
    ap.add_argument("--schemes", default=None, help=f"comma list from {','.join(SCHEMES)} (default: the preset's)")
    ap.add_argument("--cash", type=float, default=DEFAULT_CASH,
                    help=f"engine book in GBP (default {DEFAULT_CASH:,.0f}; curves are scaled to the "
                         f"{BOOK_VALUE:,.0f} thesis book)")
    ap.add_argument("--investment-cap", type=float, default=DEFAULT_INVESTMENT_CAP,
                    help=f"fraction of equity deployed (default {DEFAULT_INVESTMENT_CAP})")
    ap.add_argument("--max-ffill-gap", type=int, default=DEFAULT_MAX_FFILL_GAP,
                    help="longest run of missing levels forward-filled; a longer one is an error "
                         f"(default {DEFAULT_MAX_FFILL_GAP})")
    ap.add_argument("--strict-calendar", action="store_true",
                    help="fill nothing: keep only the days on which every included name has a level")
    ap.add_argument("--no-rescale", action="store_true",
                    help="pass the raw total-return levels to the engine (default: each column's window "
                         "minimum rescaled to 100)")
    ap.add_argument("--no-repairs", action="store_true", help="do not apply the documented level repairs")
    ap.add_argument("--no-dashboard", action="store_true", help="skip the dashboard replays")
    ap.add_argument("--exclude", default=None, metavar="TICKER,TICKER",
                    help="comma list of holdings to leave out, for a sensitivity run (recorded as "
                         "excluded_by_user; the window and every other setting stay the preset's)")
    ap.add_argument("--quick", action="store_true",
                    help=f"CI smoke: {len(QUICK_TICKERS)} names ({','.join(QUICK_TICKERS)}) over the last "
                         f"{QUICK_BARS} bars up to --end")
    return ap


def resolve(args: argparse.Namespace) -> dict:
    """The ``run_thesis`` keyword arguments for parsed CLI ``args`` (preset, overrides, --quick)."""
    p = PRESETS[args.preset]
    end = args.end or p.end
    start = args.start or p.start
    if args.quick and args.start is None:
        start = quick_start(load_panel(args.prices), end)
    exclude = tuple(t.strip() for t in (args.exclude or "").split(",") if t.strip())
    # a sensitivity run never lands in (and overwrites) the preset's own folder by default
    slug = "_".join("".join(c for c in t.lower() if c.isalnum()) for t in exclude)
    default = RESULTS_ROOT / (f"{p.name}_ex_{slug}" if exclude else p.name)
    results = Path(args.results) if args.results else (QUICK_RESULTS if args.quick else default)
    return dict(
        prices_path=args.prices, holdings_path=args.holdings, results_dir=results, start=start, end=end,
        lookback_bars=args.lookback if args.lookback is not None else p.lookback_bars,
        rebalance_every=args.rebalance_every if args.rebalance_every is not None else p.rebalance_every,
        starting_cash=args.cash, investment_cap=args.investment_cap, max_ffill_gap=args.max_ffill_gap,
        schemes=parse_schemes(args.schemes) if args.schemes else p.schemes,
        dashboard=not args.no_dashboard, tickers=QUICK_TICKERS if args.quick else None,
        exclude=exclude,
        strict_calendar=args.strict_calendar, rescale=not args.no_rescale, repairs=not args.no_repairs,
        preset=p.name,
    )


def main(argv: Sequence[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    try:
        kw = resolve(args)
        print(f"[thesis] {'QUICK ' if args.quick else ''}{kw['preset']} -> {_display_path(kw['results_dir'])}; "
              f"window {kw['start']}..{kw['end']}, lookback {kw['lookback_bars']}, schemes {', '.join(kw['schemes'])}"
              + (f"; SENSITIVITY: excluding {', '.join(kw['exclude'])}" if kw["exclude"] else ""))
        summary = run_thesis(**kw)
    except ValueError as exc:
        ap.error(str(exc))
    u = summary["universe"]
    print(f"[thesis] {u['n_included']}/{u['n_universe']} names included ({u['n_excluded']} excluded); "
          f"window {summary['window']['first_bar']}..{summary['window']['last_bar']}, first fill "
          f"{summary['window']['first_fill_date']}")
    for s, d in summary["dashboard"].items():
        print(f"[thesis] dashboard replay {s}: {d['status']}" + (f" ({d['error']})" if d.get("error") else ""))
    print(f"[thesis] {summary['status']} in {summary['runtime_seconds']['total']:.1f} s -> "
          f"{summary['outputs']['comparison_md']}")
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
