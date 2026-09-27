"""Run the loop: NautilusTrader backtest of the skfolio rebalance, curve read back from the sink.

``python -m quantstack.execution.backtest [--allocator hrp] [--start 2016-01-01] [--end 2022-12-28]``

``--allocator fixed --fixed-weights AAPL=0.4,MSFT=0.6`` (or a ``.json`` / ``.csv``
file, see :func:`parse_fixed_weights`) rebalances to that constant vector instead
of HRP; ``--symbols`` then defaults to the symbols given, and if it is passed
too, the two must name the same symbols.

What it does
------------
0. Validates the inputs before any engine is built: at least two symbols, no
   duplicates, every symbol in the dataset, a known allocator, fixed weights
   exactly when ``allocator="fixed"`` (``ValueError`` from
   :func:`run_backtest`); the CLI also checks that the window holds more
   than ``lookback_bars`` bars per symbol (the strategy trades only once it
   has ``lookback_bars`` closes) and exits with status 2 and a message
   otherwise.
1. Loads daily adjusted closes for the universe (skfolio's bundled dataset,
   see ``data.py``), builds ``Equity`` instruments (lot size 1, a price tick
   chosen per symbol from its smallest close: 0.01 for names that never trade
   below 1, finer below, see ``data.price_precision_for``) and one
   ``Bar`` per (symbol, day) directly (the ``BarDataWrangler`` is broken under
   pandas 3), plus one synthetic close trade per bar so the ``RiskEngine`` can
   price market orders.  Trades and bars go to the engine in one ``add_data``
   call per (instrument, data type): Nautilus validates only the first
   element of each call.
2. Builds a ``BacktestEngine`` (fixed trader id, logging at WARNING) with one
   simulated venue: ``OmsType.NETTING``, ``AccountType.CASH``, USD base,
   $1M starting balance, *default* fill model, no fee model, no latency model,
   default ``use_message_queue=True``.  No commissions and no slippage is the
   article's stated simplification; with close-only bars every market order
   fills exactly at the close of the bar that triggered it.
3. Adds :class:`~quantstack.execution.strategy.SkfolioRebalance` and runs.
4. Reads the equity curve *back out of the sink* (as the article did with
   Perspective), not out of the engine: the strategy publishes one equity row
   per day; a ``RecordingSink`` is used when no sink is passed, and a caller's
   sink (e.g. the dashboard's Perspective sink) is tee'd with a recorder so the
   curve can still be read back.
5. Cross-checks against the engine's own reports
   (``engine.trader.generate_order_fills_report()``, ``generate_fills_report()``,
   ``generate_positions_report()``, ``generate_account_report(venue)``): number
   of fills and final cash must agree with what the strategy saw.
6. Benchmarks: the same engine with ``allocator="equal"`` (1/N, same monthly
   schedule, same cash buffer), and a pandas equal-weight buy-and-hold of the
   same names started on the strategy's first fill date -- "the blue line that
   cannot reject a trade" (fully invested, no cash buffer, never trades).
7. Optionally reproduces the order-sequencing experiment on the full window
   (``sells_first`` and ``buys_first`` modes; see ``strategy.py``).

Fill assumption: optimistic market-on-close
-------------------------------------------
Every rebalance is sized on a day's closes and fills at that same close (the
strategy observes the close, then trades at it; no fees, no slippage).  This
is the article's simplification and it flatters the result: live, the
weights would be sized on an estimate before the close and sent as
market-on-close orders, or traded the next day at a different price.  The
summary JSON repeats this under ``notes.fill_assumption``.

Equity CSV layout (``execution_equity.csv``), defined once in :func:`equity_columns`
-------------------------------------------------------------------------------------
Written with :func:`quantstack.contracts.write_equity_csv` (read it back with
``contracts.read_equity_csv``), dollars rounded to cents::

    date, equity_<allocator>, equity_equal_engine, equity_equal_pandas

* ``equity_<allocator>`` -- the strategy's own curve, always the first
  column (``read_equity_csv(path)`` returns it by default);
* ``equity_equal_engine`` -- 1/N in the same engine, same schedule;
* ``equity_equal_pandas`` -- the pandas equal-weight buy-and-hold.

The default run writes ``date,equity_hrp,equity_equal_engine,equity_equal_pandas``.
With ``--allocator equal`` the benchmark columns are still written, and
``equity_equal_engine`` is then a copy of ``equity_equal`` (the strategy *is*
the equal-weight engine run; it is not run twice).  Every curve sits at the
starting cash until its first fill.

Version-skew notes (nautilus_trader 1.231.0 + pandas 3.0.6): ``engine.run()``
emits a ``Pandas4Warning`` (it calls the deprecated ``pd.Timestamp.utcnow``),
silenced here; Nautilus logging is initialised once per process and the first
engine's ``LoggingConfig`` wins, so the noisy order-sequencing reproduction runs
in a child interpreter with logging OFF.

Metrics are measured from the first fill date: CAGR, max drawdown,
annualised volatility (daily returns x sqrt(252)), Sharpe with rf = 0, and
turnover (one-way, annualised: 0.5 x traded notional / mean equity / years,
reported with and without the initial buy-in).

Outputs (CLI, under ``--results-dir``, default ``results/``):
``execution_equity.csv`` (layout above), ``execution_fills.csv`` (exactly the
``FILLS_SCHEMA`` columns, rows sorted by ``(ts, symbol, side, qty)`` so the
file is reproducible byte for byte), ``execution_positions.csv`` (final
``PositionSnapshot`` via ``contracts.write_positions_csv``, including the
account's cash; the risk module turns this file into an ORE portfolio),
``execution_weights_<allocator>.csv`` (target weights per rebalance: ``date``
then one column per symbol, summing to 1),
``execution_weights_<allocator>_achieved.csv`` (same layout: the book right
after that rebalance's fills, ``qty * close / equity``; whole-share flooring
and the ``investment_cap`` cash buffer keep it under the target, the gaps are
summarised under ``weight_tracking`` in the stats), ``execution_summary.json``
(its ``outputs`` block lists the paths actually written) and
``figures/execution_equity.png``.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from quantstack.contracts import (
    FILLS_SCHEMA,
    DashboardSink,
    PositionSnapshot,
    RecordingSink,
    write_equity_csv,
    write_positions_csv,
)
from quantstack.execution.data import (
    DEFAULT_BAR_VOLUME,
    DEFAULT_END,
    DEFAULT_START,
    DEFAULT_SYMBOLS,
    DEFAULT_VENUE,
    load_prices,
    make_bar_types,
    make_bars,
    make_close_trades,
    make_instruments,
    price_precisions,
    validate_symbols,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"
FIG_DIR = RESULTS_DIR / "figures"
TRADER_ID = "QUANTSTACK-001"
TRADING_DAYS = 252

ARTICLE = {
    "fills": 558,
    "start_equity": 1_000_000,
    "final_equity_hrp": 2_260_000,
    "first_fill": "2016-12",
    "cagr_hrp": 0.146,
    "max_dd_hrp": 0.323,
    "final_equity_equal_weight": 2_740_000,
    "note": "article's own 8 names and data source; not reproducible here",
}

FILL_ASSUMPTION = (
    "optimistic market-on-close: each rebalance is sized on the day's closes and fills at "
    "that same close (close-only bars, default fill model, no fees, no slippage), the "
    "article's simplification; live, sizing would use a pre-close estimate or trade the next day"
)

# ---- equity CSV layout (see the module docstring): defined here, once.
BENCHMARK_COLUMNS: tuple[str, ...] = ("equity_equal_engine", "equity_equal_pandas")
FILLS_SORT_KEYS: tuple[str, ...] = ("ts", "symbol", "side", "qty")


def equity_columns(allocator: str, benchmarks: bool = True) -> list[str]:
    """Columns of ``curves`` / ``execution_equity.csv`` (besides ``date``), in file order.

    The strategy's own curve ``equity_<allocator>`` comes first, then (with
    ``benchmarks``) ``equity_equal_engine`` and ``equity_equal_pandas``.  For
    ``allocator="equal"`` the engine benchmark duplicates the strategy column.
    """
    return [f"equity_{allocator}", *(BENCHMARK_COLUMNS if benchmarks else ())]


def check_window(prices: pd.DataFrame, lookback_bars: int) -> None:
    """Raise ``ValueError`` unless every symbol has more than ``lookback_bars`` bars.

    The strategy rebalances for the first time on the day its trailing window
    is full (``lookback_bars`` closes), so a window of at most that many bars
    never trades (or trades on its very last day, leaving no curve to measure).
    """
    n = int(prices.notna().sum().min()) if prices.shape[1] else 0
    if n <= lookback_bars:
        span = (f"{prices.index[0].date()}..{prices.index[-1].date()}" if len(prices) else "empty window")
        raise ValueError(
            f"{span} has {n} bars per symbol, but the strategy needs more than "
            f"lookback_bars={lookback_bars} (it first trades once it holds {lookback_bars} closes): "
            "start earlier or lower --lookback"
        )


def sort_fills(fills: pd.DataFrame) -> pd.DataFrame:
    """Fills in a reproducible order: stable sort by ``(ts, symbol, side, qty)``.

    ``ts`` is an ISO-8601 string with a fixed UTC offset, so the string order is
    the time order.  ``run_backtest`` keeps its ``fills`` in event order; files
    are written sorted.
    """
    return fills.sort_values(list(FILLS_SORT_KEYS), kind="stable").reset_index(drop=True)


class TeeSink:
    """Forward every update to several sinks (e.g. Perspective + a recorder)."""

    def __init__(self, *sinks: DashboardSink) -> None:
        self.sinks = [s for s in sinks if s is not None]

    def update_positions(self, rows: Iterable[dict]) -> None:
        rows = list(rows)
        for s in self.sinks:
            s.update_positions(rows)

    def update_equity(self, rows: Iterable[dict]) -> None:
        rows = list(rows)
        for s in self.sinks:
            s.update_equity(rows)

    def update_fills(self, rows: Iterable[dict]) -> None:
        rows = list(rows)
        for s in self.sinks:
            s.update_fills(rows)


# --------------------------------------------------------------------------- metrics


def perf_metrics(equity: pd.Series, start: pd.Timestamp | str | None = None) -> dict:
    """CAGR / max drawdown / vol / Sharpe (rf=0) of a daily equity curve from ``start``."""
    eq = equity.dropna().astype(float).sort_index()
    if start is not None:
        eq = eq.loc[pd.Timestamp(start):]
    if len(eq) < 2:
        return {"start_date": None, "end_date": None, "start_equity": float("nan"),
                "final_equity": float("nan"), "years": 0.0, "total_return": float("nan"),
                "cagr": float("nan"), "max_drawdown": float("nan"),
                "max_drawdown_peak": None, "max_drawdown_trough": None,
                "ann_vol": float("nan"), "sharpe": float("nan")}
    rets = eq.pct_change().dropna()
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    total = eq.iloc[-1] / eq.iloc[0] - 1.0
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0 if years > 0 else float("nan")
    dd = eq / eq.cummax() - 1.0
    trough = dd.idxmin()
    peak = eq.loc[:trough].idxmax()
    vol = float(rets.std(ddof=1) * math.sqrt(TRADING_DAYS))
    sharpe = float(rets.mean() / rets.std(ddof=1) * math.sqrt(TRADING_DAYS)) if rets.std() > 0 else float("nan")
    return {
        "start_date": eq.index[0].date().isoformat(),
        "end_date": eq.index[-1].date().isoformat(),
        "start_equity": float(eq.iloc[0]),
        "final_equity": float(eq.iloc[-1]),
        "years": float(years),
        "total_return": float(total),
        "cagr": float(cagr),
        "max_drawdown": float(-dd.min()),
        "max_drawdown_peak": peak.date().isoformat(),
        "max_drawdown_trough": trough.date().isoformat(),
        "ann_vol": vol,
        "sharpe": sharpe,
    }


def drawdown_in(equity: pd.Series, start: str, end: str) -> dict:
    """Peak-to-trough drawdown of ``equity`` with both points inside [start, end]."""
    eq = equity.loc[pd.Timestamp(start):pd.Timestamp(end)]
    if len(eq) < 2:
        return {"drawdown": float("nan"), "peak": None, "trough": None}
    dd = eq / eq.cummax() - 1.0
    trough = dd.idxmin()
    peak = eq.loc[:trough].idxmax()
    return {"drawdown": float(-dd.min()), "peak": peak.date().isoformat(),
            "trough": trough.date().isoformat()}


def turnover_stats(fills: pd.DataFrame, equity: pd.Series, first_fill: pd.Timestamp | None) -> dict:
    """Traded notional and annualised one-way turnover (with / without the initial buy-in)."""
    if fills.empty or first_fill is None:
        return {"traded_notional": 0.0, "initial_buy_in_notional": 0.0,
                "turnover_annual_oneway": 0.0, "turnover_annual_oneway_ex_initial": 0.0}
    notional = (fills["qty"].abs() * fills["price"]).astype(float)
    day = pd.to_datetime(fills["ts"]).dt.tz_convert(None).dt.normalize()
    initial = float(notional[day == day.min()].sum())
    eq = equity.loc[first_fill:]
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    mean_eq = float(eq.mean())
    total = float(notional.sum())
    return {
        "traded_notional": total,
        "initial_buy_in_notional": initial,
        "turnover_annual_oneway": 0.5 * total / mean_eq / years,
        "turnover_annual_oneway_ex_initial": 0.5 * (total - initial) / mean_eq / years,
    }


def equal_weight_pandas(prices: pd.DataFrame, start: pd.Timestamp, starting_cash: float) -> pd.Series:
    """Equal-weight buy-and-hold from ``start`` (flat cash before it), the pandas one-liner.

    ``starting_cash * (prices.loc[start:] / prices.loc[start]).mean(axis=1)``:
    fully invested on day one in 1/N of each name, never rebalanced, never
    rejected.  Before ``start`` the curve sits at ``starting_cash`` so it lines
    up with the engine curves, which are in cash until their first fill.
    """
    start = pd.Timestamp(start)
    bh = starting_cash * (prices.loc[start:] / prices.loc[start]).mean(axis=1)
    pre = pd.Series(float(starting_cash), index=prices.index[prices.index < start])
    return pd.concat([pre, bh]).astype(float)


def equal_weight_daily_rebalanced(prices: pd.DataFrame, start: pd.Timestamp, starting_cash: float) -> pd.Series:
    """The other classic one-liner: daily-rebalanced 1/N index from ``start``."""
    r = prices.loc[pd.Timestamp(start):].pct_change().fillna(0.0).mean(axis=1)
    return starting_cash * (1.0 + r).cumprod()


WEIGHT_TRACKING_BASIS = (
    "gap = investment_cap * target - achieved, in fractions of equity, per symbol and rebalance; "
    "achieved = qty * close / equity right after that rebalance's fills (same close); "
    "> 0 means under target (whole-share flooring, e.g. a high-priced name with a small weight)"
)


def weight_tracking(targets: Sequence[Mapping], achieved: Sequence[Mapping], investment_cap: float) -> dict:
    """How far the book landed from the target weights at each rebalance.

    ``targets`` and ``achieved`` are the strategy's ``weights_history`` and
    ``achieved_history`` (rows ``{"date": ..., <symbol>: weight}``), matched
    by date.  The orders aim at ``investment_cap * target`` of equity (the
    rest is the cash buffer), so that is what achieved weights are compared
    with (see :data:`WEIGHT_TRACKING_BASIS`).  Returns the overall mean and
    max absolute gap (and where the max happened), the mean invested fraction
    after rebalancing, and per symbol ``mean_capped_target`` (mean of
    ``investment_cap * target``), ``mean_achieved``, ``mean_abs_gap`` and
    ``max_abs_gap``.
    """
    t = pd.DataFrame(list(targets))
    a = pd.DataFrame(list(achieved))
    out = {"basis": WEIGHT_TRACKING_BASIS, "investment_cap": float(investment_cap), "n_rebalances": 0,
           "mean_abs_gap": float("nan"), "max_abs_gap": float("nan"), "max_abs_gap_symbol": None,
           "max_abs_gap_date": None, "mean_invested_fraction": float("nan"), "per_symbol": {}}
    if t.empty or a.empty:
        return out
    t, a = t.set_index("date"), a.set_index("date")
    dates = [d for d in t.index if d in a.index]
    if not dates:
        return out
    t = t.loc[dates].astype(float) * float(investment_cap)
    a = a.reindex(index=dates, columns=t.columns).astype(float).fillna(0.0)
    gap = (t - a).abs()
    stacked = gap.stack()
    where = stacked.idxmax()
    out.update({
        "n_rebalances": len(dates),
        "mean_abs_gap": float(stacked.mean()),
        "max_abs_gap": float(stacked.max()),
        "max_abs_gap_date": str(where[0]),
        "max_abs_gap_symbol": str(where[1]),
        "mean_invested_fraction": float(a.sum(axis=1).mean()),
        "per_symbol": {str(sym): {"mean_capped_target": float(t[sym].mean()), "mean_achieved": float(a[sym].mean()),
                                  "mean_abs_gap": float(gap[sym].mean()), "max_abs_gap": float(gap[sym].max())}
                       for sym in t.columns},
    })
    return out


# --------------------------------------------------------------------------- engine


@dataclass
class EngineRun:
    equity: pd.Series
    fills: pd.DataFrame
    snapshot: PositionSnapshot | None
    stats: dict
    reports: dict


def _engine_run(
    prices: pd.DataFrame,
    allocator: str,
    starting_cash: float,
    sink: DashboardSink | None,
    lookback_bars: int,
    rebalance_every: int,
    investment_cap: float,
    order_mode: str,
    risk_checks: bool,
    bar_volume: int,
    venue_name: str,
    log_level: str = "WARNING",
    fixed_weights: Mapping[str, float] | None = None,
) -> EngineRun:
    from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.model.currencies import USD
    from nautilus_trader.model.enums import AccountType, OmsType
    from nautilus_trader.model.identifiers import TraderId, Venue
    from nautilus_trader.model.objects import Money

    from quantstack.execution.strategy import SkfolioRebalance, SkfolioRebalanceConfig

    from quantstack.execution.strategy import normalise_fixed_weights

    symbols = list(prices.columns)
    precisions = price_precisions(prices)  # tick per symbol from its smallest close (data.py)
    instruments = make_instruments(symbols, venue_name, price_precision=precisions)
    bar_types = make_bar_types(instruments)
    bars = make_bars(prices, instruments, bar_types, volume=bar_volume)  # refuses closes rounding to <= 0
    trades = make_close_trades(bars, bar_volume) if risk_checks else []
    # Grouped per instrument for add_data (see below); order within a symbol is by day.
    bars_by_symbol: dict[str, list] = {s: [] for s in symbols}
    trades_by_symbol: dict[str, list] = {s: [] for s in symbols}
    for b in bars:
        bars_by_symbol[b.bar_type.instrument_id.symbol.value].append(b)
    for t in trades:
        trades_by_symbol[t.instrument_id.symbol.value].append(t)

    # largest relative change rounding made to a close, per symbol (the bars vs the raw panel)
    rounding_err = {}
    for sym in symbols:
        raw = prices[sym].to_numpy(dtype=float)
        raw = raw[~np.isnan(raw)]
        got = np.array([float(b.close) for b in bars_by_symbol[sym]])
        rounding_err[str(sym)] = float(np.max(np.abs(got - raw) / raw)) if raw.size else 0.0

    recorder = RecordingSink()
    tee = TeeSink(sink, recorder) if sink is not None else recorder

    engine = BacktestEngine(
        BacktestEngineConfig(
            trader_id=TraderId(TRADER_ID),
            logging=LoggingConfig(log_level=log_level, log_colors=False,
                                  # bars-only runs warn once per order otherwise.  NB: Nautilus
                                  # logging is process-global -- the FIRST engine's LoggingConfig
                                  # wins for the whole interpreter (hence the subprocess below).
                                  log_component_levels={"RiskEngine": "ERROR"} if not risk_checks else None),
            run_analysis=False,
        )
    )
    venue = Venue(venue_name)
    try:
        engine.add_venue(
            venue=venue,
            oms_type=OmsType.NETTING,
            account_type=AccountType.CASH,
            base_currency=USD,
            starting_balances=[Money(starting_cash, USD)],
        )
        for inst in instruments.values():
            engine.add_instrument(inst)
        # One add_data call per (instrument, data type): Nautilus validates only
        # data[0] of each call (instrument in the cache, EXTERNAL bar source) and
        # registers only that instrument as having data.  sort=False, then one
        # sort_data(): Python's stable sort by ts_init keeps the call order within
        # a timestamp -- every close trade, then the bars in column order -- so
        # each symbol's last-trade price is cached before any bar reaches the
        # strategy, and the last symbol's bar still completes the day.
        for sym in symbols:
            if trades_by_symbol[sym]:
                engine.add_data(trades_by_symbol[sym], sort=False)
        for sym in symbols:
            if bars_by_symbol[sym]:
                engine.add_data(bars_by_symbol[sym], sort=False)
        engine.sort_data()
        cfg = SkfolioRebalanceConfig(
            instrument_ids=[instruments[s].id for s in symbols],
            bar_types=[bar_types[s] for s in symbols],
            lookback_bars=lookback_bars,
            rebalance_every=rebalance_every,
            investment_cap=investment_cap,
            allocator=allocator,
            order_mode=order_mode,
            fixed_weights=(None if fixed_weights is None
                           else {str(k): float(v) for k, v in fixed_weights.items()}),
        )
        strat = SkfolioRebalance(cfg, sink=tee)
        engine.add_strategy(strat)
        t0 = time.perf_counter()
        with warnings.catch_warnings():
            # nautilus 1.231 calls pd.Timestamp.utcnow(), deprecated in pandas 3
            # (Pandas4Warning); harmless, silenced so the CLI output stays readable.
            warnings.filterwarnings("ignore", message=".*Timestamp.utcnow is deprecated.*")
            engine.run()
        runtime = time.perf_counter() - t0

        fills_report = engine.trader.generate_fills_report()
        order_fills_report = engine.trader.generate_order_fills_report()
        positions_report = engine.trader.generate_positions_report()
        account_report = engine.trader.generate_account_report(venue)
        account = engine.portfolio.account(venue)
        final_cash_engine = float(account.balance_total(USD).as_double()) if account else float("nan")
    finally:
        engine.dispose()

    equity = recorder.equity_curve()
    fills = pd.DataFrame(strat.fills, columns=["ts", "symbol", "side", "qty", "price"])
    last_day = prices.index[-1].date().isoformat()
    halted = equity.empty or equity.index[-1].date().isoformat() != last_day
    stats = {
        "allocator": allocator,
        "order_mode": order_mode,
        "risk_checks": risk_checks,
        "n_orders": len(strat.submitted),
        "n_fills": strat.n_fills,
        "n_rejected": strat.n_rejected,
        "n_denied": strat.n_denied,
        "n_canceled": strat.n_canceled,
        "rejections_sample": strat.rejections[:5],
        "n_rebalances": len(strat.rebalance_dates),
        "first_rebalance": strat.rebalance_dates[0].isoformat() if strat.rebalance_dates else None,
        "first_fill_date": fills["ts"].iloc[0][:10] if not fills.empty else None,
        "hrp_fit_seconds_total": float(sum(strat.fit_seconds)),
        "hrp_fit_seconds_mean": float(np.mean(strat.fit_seconds)) if strat.fit_seconds else 0.0,
        "engine_run_seconds": runtime,
        "days_published": strat.published_days,
        "halted_early": bool(halted),
        "last_published_day": equity.index[-1].date().isoformat() if not equity.empty else None,
        "final_cash": strat.last_snapshot.cash if strat.last_snapshot else float("nan"),
        "final_cash_engine_account": final_cash_engine,
        "fills_report_rows": int(len(fills_report)),
        "order_fills_report_rows": int(len(order_fills_report)),
        "positions_report_rows": int(len(positions_report)),
        "account_report_rows": int(len(account_report)),
        "max_equity_check_diff_vs_portfolio": float(strat.max_equity_check_diff),
        "n_equity_checks": int(strat.n_equity_checks),
        "price_precision": precisions,
        "close_rounding_max_rel_error": rounding_err,
        "fixed_weights_normalised": (None if fixed_weights is None
                                     else normalise_fixed_weights(fixed_weights, symbols)),
        "weight_tracking": weight_tracking(strat.weights_history, strat.achieved_history, investment_cap),
        "weights_history": strat.weights_history,
        "achieved_weights_history": strat.achieved_history,
        "submitted": strat.submitted,
    }
    snap = strat.last_snapshot
    if snap is not None:
        snap = PositionSnapshot(
            as_of=snap.as_of,
            positions=[p for p in snap.positions if p.qty != 0],
            cash=snap.cash,
        )
    return EngineRun(equity, fills, snap, stats,
                     {"fills": fills_report, "order_fills": order_fills_report,
                      "positions": positions_report, "account": account_report})


def run_backtest(
    symbols: Sequence[str] | None = None,
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    allocator: str = "hrp",
    starting_cash: float = 1_000_000,
    sink: DashboardSink | None = None,
    lookback_bars: int = 252,
    rebalance_every: int = 21,
    investment_cap: float = 0.98,
    order_mode: str = "two_phase",
    risk_checks: bool = True,
    bar_volume: int = DEFAULT_BAR_VOLUME,
    venue: str = DEFAULT_VENUE,
    benchmarks: bool = True,
    prices: pd.DataFrame | None = None,
    log_level: str = "WARNING",
    fixed_weights: Mapping[str, float] | None = None,
) -> dict:
    """Backtest ``allocator`` on ``symbols`` over [start, end]; return curves and metrics.

    The universe: without ``prices``, ``symbols`` (default
    ``data.DEFAULT_SYMBOLS``) loaded from skfolio's dataset over
    [``start``, ``end``].  With ``prices`` (a NaN-free panel, one column per
    symbol), its columns are the universe, in column order, and its index is
    the window (``start`` / ``end`` are not used); ``symbols`` may then be
    left ``None``, and if it is given it must name the same symbols as
    ``prices.columns`` (compared after strip / upper-case, order free), else
    ``ValueError`` listing the symbols on each side only.

    Inputs are validated before any engine is built (``ValueError``): at least
    two symbols, no duplicates, all in the dataset, a known
    ``allocator`` / ``order_mode``, ``lookback_bars >= 3``,
    ``rebalance_every >= 1``, and ``fixed_weights`` given exactly when
    ``allocator="fixed"`` (see ``strategy.check_fixed_weights``): a mapping
    symbol -> weight whose keys are exactly the universe (0 allowed, a key
    outside the universe is an error that lists the extra and missing
    symbols), with finite non-negative values.  Fixed weights are relative,
    rescaled to sum to 1 (recorded as ``stats["fixed_weights_normalised"]``),
    and the strategy rebalances back to them on the usual schedule; the
    equal-weight benchmark run never sees them.  A close that is not positive
    at its instrument's price precision raises ``ValueError`` naming the
    symbol and date (``data.make_bars``).  A window too short to trade (see
    :func:`check_window`) is *not* an error here: the engine runs, nothing
    trades, and the result has the same keys with zero fills and empty curves.

    Returns a dict with always the same keys:

    * ``equity``   -- pd.Series read back from the sink (flat at the starting
      cash until the first fill);
    * ``fills``    -- DataFrame with the ``FILLS_SCHEMA`` columns, in event
      order (possibly empty);
    * ``snapshot`` -- final ``PositionSnapshot`` (non-zero lines, the
      account's final ``cash``);
    * ``metrics`` (from the first fill; over the whole flat curve if nothing
      traded), ``stats`` (counts, runtimes, cross-checks, per-symbol
      ``price_precision`` and ``close_rounding_max_rel_error``, target
      ``weights_history`` and ``achieved_weights_history`` per rebalance and
      their ``weight_tracking`` summary, see :func:`weight_tracking`), ``reports``
      (Nautilus report DataFrames), ``prices``, ``first_fill`` (Timestamp or
      None), ``runtime_seconds``;
    * ``curves``   -- DataFrame indexed by ``date`` with the columns
      :func:`equity_columns` ``(allocator, benchmarks)``; zero rows when
      nothing traded (the benchmarks are anchored at the first fill);
    * ``equal_engine`` / ``equal_pandas`` -- benchmark sub-results
      (``equity``, ``metrics``, ...) with ``benchmarks=True`` and at least one
      fill, else None.  For ``allocator="equal"``, ``equal_engine`` is the
      main run itself (not re-run).

    ``sink`` receives every update live (a recorder is tee'd alongside it).
    """
    from quantstack.execution.strategy import ALLOCATORS, ORDER_MODES, check_fixed_weights

    t_all = time.perf_counter()
    if allocator not in ALLOCATORS:
        raise ValueError(f"allocator must be one of {ALLOCATORS}, got {allocator!r}")
    check_fixed_weights(allocator, fixed_weights)
    if order_mode not in ORDER_MODES:
        raise ValueError(f"order_mode must be one of {ORDER_MODES}, got {order_mode!r}")
    if lookback_bars < 3 or rebalance_every < 1:
        raise ValueError(f"lookback_bars must be >= 3 and rebalance_every >= 1, got "
                         f"{lookback_bars} and {rebalance_every}")
    if prices is None:
        prices = load_prices(validate_symbols(DEFAULT_SYMBOLS if symbols is None else symbols), start, end)
    else:
        columns = validate_symbols(prices.columns)
        if symbols is not None:
            wanted = validate_symbols(symbols)
            only_symbols = sorted(set(wanted) - set(columns))
            only_prices = sorted(set(columns) - set(wanted))
            if only_symbols or only_prices:
                raise ValueError(f"symbols and prices.columns name different universes: in symbols only "
                                 f"{only_symbols}, in prices.columns only {only_prices} (pass symbols=None "
                                 "to trade the panel's columns)")
    check_fixed_weights(allocator, fixed_weights, prices.columns)
    kw = dict(starting_cash=starting_cash, lookback_bars=lookback_bars,
              rebalance_every=rebalance_every, investment_cap=investment_cap,
              order_mode=order_mode, risk_checks=risk_checks, bar_volume=bar_volume,
              venue_name=venue, log_level=log_level)
    main = _engine_run(prices, allocator, sink=sink, fixed_weights=fixed_weights, **kw)
    first_fill = pd.Timestamp(main.stats["first_fill_date"]) if main.stats["first_fill_date"] else None
    out = {
        "equity": main.equity,
        "fills": main.fills,
        "snapshot": main.snapshot,
        "stats": main.stats,
        "reports": main.reports,
        "prices": prices,
        "first_fill": first_fill,
        "metrics": {**perf_metrics(main.equity, first_fill),
                    **turnover_stats(main.fills, main.equity, first_fill)},
        "equal_engine": None,
        "equal_pandas": None,
    }
    cols = equity_columns(allocator, benchmarks)
    if first_fill is None:
        # nothing traded: same keys, empty curves (nothing to anchor a benchmark on)
        out["curves"] = pd.DataFrame(index=pd.DatetimeIndex([], name="date"), columns=cols, dtype=float)
    elif not benchmarks:
        out["curves"] = pd.DataFrame({cols[0]: main.equity}).rename_axis("date")
    else:
        # the equal-weight engine benchmark; for allocator="equal" it *is* the main run
        other = main if allocator == "equal" else _engine_run(prices, "equal", sink=None, **kw)
        ew_bh = equal_weight_pandas(prices, first_fill, starting_cash)
        ew_daily = equal_weight_daily_rebalanced(prices, first_fill, starting_cash)
        other_ff = pd.Timestamp(other.stats["first_fill_date"]) if other.stats["first_fill_date"] else first_fill
        out["equal_engine"] = {
            "equity": other.equity, "fills": other.fills, "stats": other.stats,
            "metrics": {**perf_metrics(other.equity, first_fill),
                        **turnover_stats(other.fills, other.equity, other_ff)},
        }
        out["equal_pandas"] = {
            "equity": ew_bh,
            "metrics": perf_metrics(ew_bh, first_fill),
            "daily_rebalanced_metrics": perf_metrics(ew_daily, first_fill),
        }
        out["curves"] = pd.DataFrame(dict(zip(cols, (main.equity, other.equity, ew_bh)))).rename_axis("date")
    out["runtime_seconds"] = time.perf_counter() - t_all
    return out


def write_results(res: dict, results_dir: str | Path) -> dict[str, Path]:
    """Write a run's data files into ``results_dir``; return ``{output name: path}``.

    * ``equity_csv``    -- ``res["curves"]`` rounded to cents, through
      :func:`quantstack.contracts.write_equity_csv` (layout: :func:`equity_columns`);
    * ``fills_csv``     -- exactly the ``FILLS_SCHEMA`` columns (the dashboard
      replays this file into a Perspective table built from that schema),
      rows sorted by :func:`sort_fills`;
    * ``positions_csv`` -- the final snapshot, cash included, through
      :func:`quantstack.contracts.write_positions_csv`;
    * ``weights_csv``   -- the allocator's target weights at every rebalance
      (``date`` + one column per symbol, unchanged layout);
    * ``achieved_weights_csv`` -- ``execution_weights_<allocator>_achieved.csv``,
      the same layout holding the weights actually held right after each
      rebalance's fills (``stats["achieved_weights_history"]``).
    """
    results = Path(results_dir)
    results.mkdir(parents=True, exist_ok=True)
    allocator = res["stats"]["allocator"]
    paths = {
        "equity_csv": results / "execution_equity.csv",
        "fills_csv": results / "execution_fills.csv",
        "positions_csv": results / "execution_positions.csv",
        "weights_csv": results / f"execution_weights_{allocator}.csv",
        "achieved_weights_csv": results / f"execution_weights_{allocator}_achieved.csv",
    }
    write_equity_csv(res["curves"].round(2), paths["equity_csv"])
    sort_fills(res["fills"])[list(FILLS_SCHEMA)].to_csv(paths["fills_csv"], index=False,
                                                        float_format="%.4f")
    write_positions_csv(res["snapshot"], paths["positions_csv"])
    targets = pd.DataFrame(res["stats"]["weights_history"])
    targets.to_csv(paths["weights_csv"], index=False, float_format="%.6f")
    columns = list(targets.columns) or ["date", *map(str, res["prices"].columns)]
    pd.DataFrame(res["stats"].get("achieved_weights_history", []), columns=columns).to_csv(
        paths["achieved_weights_csv"], index=False, float_format="%.6f")
    return paths


# --------------------------------------------------------------------------- figure

LIGHT = {
    "surface": "#fcfcfb", "text": "#0b0b0b", "text2": "#52514e", "grid": "#e4e3df",
    "s1": "#2a78d6", "s2": "#eb6834", "s3": "#1baf7a", "shade": "#f0efec",
}


STRATEGY_LABELS = {  # allocator -> (legend label, title name)
    "hrp": ("HRP in NautilusTrader", "HRP"),
    "equal": ("Equal weight in NautilusTrader (monthly)", "monthly equal weight"),
    "fixed": ("Fixed weights (user-supplied) in NautilusTrader", "fixed weights"),
}


def plot_equity(curves: pd.DataFrame, first_fill: pd.Timestamp, path: Path, title_extra: str = "") -> Path:
    """Equity curves on a log scale + an underwater (drawdown) panel.

    ``curves`` follows :func:`equity_columns`: the first column is the
    strategy, then the two equal-weight benchmarks (the engine benchmark is
    not drawn when it duplicates the strategy, i.e. for ``allocator="equal"``).
    No global matplotlib state is touched: the figure is a bare ``Figure`` on
    an Agg canvas (no pyplot, no ``matplotlib.use``) and the styling lives in
    an ``rc_context`` that is undone on exit.
    """
    import matplotlib
    import matplotlib.dates as mdates
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator, PercentFormatter

    c = LIGHT
    main_col = str(curves.columns[0])
    allocator = main_col.removeprefix("equity_")
    label, title_name = STRATEGY_LABELS.get(allocator, (f"{allocator} in NautilusTrader", allocator))
    series = [
        ("equity_equal_pandas", "Equal weight, pandas buy-and-hold", c["s1"]),
        (main_col, label, c["s2"]),
        ("equity_equal_engine", "Equal weight in NautilusTrader (monthly)", c["s3"]),
    ]
    series = [s for s in series if s[0] in curves.columns]
    if allocator == "equal":  # the engine benchmark is a copy of the strategy column
        series = [s for s in series if s[0] != "equity_equal_engine"]
    df = curves.loc[pd.Timestamp(first_fill) - pd.Timedelta(days=45):]

    style = {"font.size": 9, "axes.edgecolor": c["text2"], "axes.labelcolor": c["text2"],
             "xtick.color": c["text2"], "ytick.color": c["text2"]}
    with matplotlib.rc_context(style):
        fig = Figure(figsize=(9, 6.2))
        FigureCanvasAgg(fig)
        ax, axd = fig.subplots(2, 1, sharex=True,
                               gridspec_kw={"height_ratios": [3, 1.3], "hspace": 0.08})
        fig.patch.set_facecolor(c["surface"])
        for a in (ax, axd):
            a.set_facecolor(c["surface"])
            a.grid(True, color=c["grid"], linewidth=0.6)
            for side in ("top", "right"):
                a.spines[side].set_visible(False)

        # shade the two stress windows so the drawdowns are easy to find
        stress = [("2020-02-19", "2020-03-23", "COVID crash"), ("2022-01-03", "2022-10-12", "2022 bear market")]
        for s0, s1, label in stress:
            if pd.Timestamp(s1) >= df.index[0] and pd.Timestamp(s0) <= df.index[-1]:
                for a in (ax, axd):
                    a.axvspan(pd.Timestamp(s0), pd.Timestamp(s1), color=c["shade"], zorder=0)
                ax.text(pd.Timestamp(s0), 1.0, " " + label, transform=ax.get_xaxis_transform(),
                        va="top", ha="left", fontsize=8, color=c["text2"])

        ends = []
        for col, label, color in series:
            s = df[col].dropna()
            ax.plot(s.index, s.values, color=color, linewidth=1.6, label=label)
            ends.append((float(np.log10(s.iloc[-1])), s.iloc[-1], s.index[-1], color))
            dd = s.loc[pd.Timestamp(first_fill):] / s.loc[pd.Timestamp(first_fill):].cummax() - 1.0
            axd.plot(dd.index, dd.values, color=color, linewidth=1.2)
        # direct end labels, nudged apart in log space so they never collide
        lo, hi = np.log10(df[[s[0] for s in series]].min().min()), np.log10(df[[s[0] for s in series]].max().max())
        gap = 0.045 * (hi - lo)
        placed: list[float] = []
        for y_log, v, x, color in sorted(ends, key=lambda e: e[0]):
            y = max([y_log] + [p + gap for p in placed])
            placed.append(y)
            # colored dot carries identity, the value stays in text ink
            ax.plot([x + pd.Timedelta(days=22)], [10 ** y], marker="o", markersize=5, color=color,
                    clip_on=False, zorder=5)
            ax.annotate(f"${v / 1e6:.2f}M", xy=(x + pd.Timedelta(days=40), 10 ** y), va="center",
                        ha="left", fontsize=8, color=c["text"], annotation_clip=False)
        ax.axvline(pd.Timestamp(first_fill), color=c["text2"], linewidth=0.8, linestyle=":")
        ax.set_yscale("log")
        ax.yaxis.set_major_locator(FixedLocator([0.8e6, 1e6, 1.25e6, 1.5e6, 2e6, 2.5e6, 3e6, 4e6, 5e6]))
        ax.yaxis.set_minor_locator(NullLocator())
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v / 1e6:g}M"))
        ax.set_ylabel("Equity (log scale)")
        ax.legend(loc="upper left", bbox_to_anchor=(0.0, 0.93), frameon=False, fontsize=8, labelcolor=c["text"])
        ax.set_title(f"Equity from first fill: {title_name} vs equal weight" + title_extra,
                     loc="left", fontsize=11, color=c["text"])
        axd.set_ylabel("Drawdown")
        axd.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
        axd.xaxis.set_major_locator(mdates.YearLocator())
        axd.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        axd.set_xlabel("Date")
        fig.subplots_adjust(left=0.1, right=0.88, top=0.93, bottom=0.08)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=120, facecolor=c["surface"])
    return path




# --------------------------------------------------------------------------- sequencing experiment


def sequencing_experiment(
    symbols: Sequence[str], start: str, end: str, allocator: str = "hrp",
    starting_cash: float = 1_000_000, lookback_bars: int = 252, rebalance_every: int = 21,
    investment_cap: float = 0.98, modes: Sequence[str] = ("sells_first", "buys_first"),
    log_level: str = "OFF", fixed_weights: Mapping[str, float] | None = None,
) -> dict:
    """Re-run the backtest with the naive order sequencings (see ``strategy.py``)."""
    prices = load_prices(symbols, start, end)
    out = {}
    for mode in modes:
        r = run_backtest(symbols, start, end, allocator=allocator, starting_cash=starting_cash,
                         lookback_bars=lookback_bars, rebalance_every=rebalance_every,
                         investment_cap=investment_cap, order_mode=mode, benchmarks=False,
                         prices=prices, log_level=log_level, fixed_weights=fixed_weights)
        st = r["stats"]
        row = {k: st[k] for k in ("n_orders", "n_fills", "n_denied", "n_rejected",
                                  "halted_early", "last_published_day")}
        row["final_equity"] = float(r["equity"].iloc[-1]) if not r["equity"].empty else None
        row["rejections_sample"] = st["rejections_sample"][:2]
        out[mode] = row
    return out


def run_sequencing_experiment_subprocess(symbols, start, end, allocator, cash, lookback,
                                         rebalance_every, investment_cap, fixed_weights=None) -> dict:
    """Run :func:`sequencing_experiment` in a fresh interpreter with logging OFF."""
    import subprocess

    args = json.dumps([[list(symbols), start, end, allocator, cash, lookback,
                        rebalance_every, investment_cap],
                       {"fixed_weights": None if fixed_weights is None else dict(fixed_weights)}])
    code = ("import json,sys; from quantstack.execution.backtest import sequencing_experiment as f; "
            "a,k=json.loads(sys.argv[1]); print('@@'+json.dumps(f(*a,**k)))")
    proc = subprocess.run([sys.executable, "-c", code, args], capture_output=True, text=True,
                          cwd=str(REPO_ROOT), timeout=600)
    for ln in proc.stdout.splitlines():
        if ln.startswith("@@"):
            return json.loads(ln[2:])
    raise RuntimeError(f"sequencing experiment failed:\n{proc.stderr[-2000:]}")


# --------------------------------------------------------------------------- CLI


def _round(obj, nd=6):
    if isinstance(obj, float):
        return round(obj, nd) if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _round(v, nd) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round(v, nd) for v in obj]
    return obj


def _versions() -> dict:
    import nautilus_trader
    import skfolio

    return {"nautilus_trader": nautilus_trader.__version__, "skfolio": skfolio.__version__,
            "pandas": pd.__version__, "numpy": np.__version__, "python": sys.version.split()[0]}


def _public_stats(stats: dict) -> dict:
    return {k: v for k, v in stats.items()
            if k not in ("weights_history", "achieved_weights_history", "submitted")}


class _JsonPairs(list):
    """A JSON object as the list of its ``(key, value)`` pairs (``object_pairs_hook``), duplicates kept."""


def parse_fixed_weights(spec: str) -> dict[str, float]:
    """``--fixed-weights`` -> ``{SYMBOL: weight}``, symbols stripped and upper-cased (as ``--symbols``).

    ``spec`` is one of:

    * inline pairs: ``"AAPL=0.25,MSFT=0.75"``;
    * a ``.json`` file holding one object: ``{"AAPL": 0.25, "MSFT": 0.75}``;
    * a ``.csv`` file whose header names the columns ``symbol`` and ``weight``.

    Files are read as UTF-8 with an optional byte-order mark (Excel's "CSV
    UTF-8" export writes one).  Only the syntax is checked here (numbers, no
    duplicate symbols -- also a key repeated inside the JSON object, which
    ``json`` would otherwise resolve silently as last-wins -- at least one
    entry); the values are checked by ``strategy.check_fixed_weights``.
    Raises ``ValueError``.
    """
    spec = spec.strip()
    path = Path(spec)
    suffix = path.suffix.lower()
    if suffix in (".json", ".csv"):
        if not path.is_file():
            raise ValueError(f"--fixed-weights file not found: {spec}")
        if suffix == ".json":
            try:
                # every JSON object comes back as its list of (key, value) pairs, repeats included,
                # so the duplicate check below sees {"AAPL": 0.9, "AAPL": 0.1} (json keeps only 0.1)
                data = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_JsonPairs)
            except json.JSONDecodeError as exc:
                raise ValueError(f"--fixed-weights {spec}: not valid JSON ({exc})") from None
            if not isinstance(data, _JsonPairs):
                raise ValueError(f'--fixed-weights {spec}: expected one JSON object {{"SYM": weight, ...}}')
            pairs = list(data)
        else:
            with path.open(newline="", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                cols = {str(c).strip().lower(): c for c in reader.fieldnames or []}
                if not {"symbol", "weight"} <= set(cols):
                    raise ValueError(f"--fixed-weights {spec}: need a header with columns symbol,weight, "
                                     f"got {reader.fieldnames}")
                pairs = [(row[cols["symbol"]], row[cols["weight"]]) for row in reader]
    else:
        pairs = []
        for item in spec.split(","):
            if not item.strip():
                continue
            sym, sep, w = item.partition("=")
            if not sep:
                raise ValueError(f"--fixed-weights: expected SYM=WEIGHT pairs or a .json / .csv file, "
                                 f"got {item.strip()!r}")
            pairs.append((sym, w))
    out: dict[str, float] = {}
    for sym, w in pairs:
        sym = str(sym if sym is not None else "").strip().upper()
        if not sym:
            raise ValueError(f"--fixed-weights: empty symbol (weight {w!r})")
        if sym in out:
            raise ValueError(f"--fixed-weights: duplicate symbol {sym}")
        try:
            if isinstance(w, bool):
                raise TypeError
            out[sym] = float(w)
        except (TypeError, ValueError):
            raise ValueError(f"--fixed-weights: weight for {sym} is not a number: {w!r}") from None
    if not out:
        raise ValueError("--fixed-weights: no SYM=WEIGHT entries")
    return out


def _display_path(path: Path) -> str:
    """Repo-relative for paths inside the repo (``results/...``), else absolute."""
    path = Path(path).resolve()
    return str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)


def main(argv: Sequence[str] | None = None, *, sink: DashboardSink | None = None) -> dict:
    """The CLI.  Bad inputs (universe, window shorter than ``--lookback``) exit with status 2.

    ``sink`` is not a command-line option.  It lets an in-process driver
    (``scripts/run_all.py``) stream the strategy run live into a dashboard
    (``run_backtest(..., sink=sink)``) while this function still writes exactly
    the files the CLI writes.  The benchmark and sequencing runs never see it.
    """
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--allocator", default="hrp", choices=["hrp", "equal", "fixed"])
    ap.add_argument("--fixed-weights", metavar="SPEC",
                    help="with --allocator fixed (and only then): SYM=W,SYM2=W2 or a .json file "
                         '{"SYM": W, ...} or a .csv file with columns symbol,weight; weights are '
                         "relative (rescaled to sum to 1)")
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=DEFAULT_END)
    ap.add_argument("--symbols", default=None,
                    help=f"comma-separated universe (default {','.join(DEFAULT_SYMBOLS)}; "
                         "with --allocator fixed, the --fixed-weights symbols)")
    ap.add_argument("--cash", type=float, default=1_000_000)
    ap.add_argument("--lookback", type=int, default=252)
    ap.add_argument("--rebalance-every", type=int, default=21)
    ap.add_argument("--investment-cap", type=float, default=0.98)
    ap.add_argument("--no-sequencing-experiment", action="store_true",
                    help="skip the sells_first / buys_first reproduction runs")
    ap.add_argument("--results-dir", default=str(RESULTS_DIR))
    args = ap.parse_args(argv)

    results = Path(args.results_dir)
    figs = results / "figures"
    t0 = time.perf_counter()
    # ---- validate before any engine is built (argparse's error(): message + exit status 2)
    from quantstack.execution.strategy import check_fixed_weights, normalise_fixed_weights

    fixed = None
    try:
        if args.allocator == "fixed" and args.fixed_weights is None:
            raise ValueError("--allocator fixed needs --fixed-weights (SYM=W,... or a .json / .csv file)")
        if args.fixed_weights is not None and args.allocator != "fixed":
            raise ValueError(f"--fixed-weights is only used with --allocator fixed, not {args.allocator}")
        if args.fixed_weights is not None:
            fixed = parse_fixed_weights(args.fixed_weights)
            check_fixed_weights(args.allocator, fixed)
        universe = args.symbols if args.symbols is not None else ",".join(fixed or DEFAULT_SYMBOLS)
        symbols = validate_symbols([s for s in universe.split(",") if s.strip()])
        check_fixed_weights(args.allocator, fixed, symbols)
        if args.lookback < 3 or args.rebalance_every < 1:
            raise ValueError("--lookback must be >= 3 and --rebalance-every >= 1")
        prices = load_prices(symbols, args.start, args.end)
        check_window(prices, args.lookback)
    except ValueError as exc:
        ap.error(str(exc))
    res = run_backtest(symbols, args.start, args.end, allocator=args.allocator,
                       starting_cash=args.cash, lookback_bars=args.lookback,
                       rebalance_every=args.rebalance_every, investment_cap=args.investment_cap,
                       prices=prices, sink=sink, fixed_weights=fixed)
    if res["first_fill"] is None:  # not expected once check_window passed; never write empty files
        ap.exit(2, f"{ap.prog}: error: the backtest produced no fills "
                   f"(orders {res['stats']['n_orders']}, denied {res['stats']['n_denied']}, "
                   f"rejected {res['stats']['n_rejected']}); nothing written\n")
    alloc = args.allocator
    main_key, other_key = alloc, "equal_engine"
    cols = equity_columns(alloc)

    # ---- files
    paths = write_results(res, results)
    paths["figure"] = plot_equity(res["curves"], res["first_fill"], figs / "execution_equity.png",
                                  title_extra=f", {len(symbols)} US large caps")

    # ---- order-sequencing experiment (full window, same allocator), in a child
    # process: Nautilus logging is process-global and the first engine's
    # LoggingConfig wins, so a quiet run needs its own interpreter.
    seq = {}
    if not args.no_sequencing_experiment:
        seq = run_sequencing_experiment_subprocess(
            symbols, args.start, args.end, alloc, args.cash, args.lookback,
            args.rebalance_every, args.investment_cap, fixed_weights=fixed)
        st = res["stats"]
        seq["two_phase"] = {k: st[k] for k in ("n_orders", "n_fills", "n_denied", "n_rejected",
                                               "halted_early", "last_published_day")}
        seq["two_phase"]["final_equity"] = float(res["equity"].iloc[-1])

    m_main, m_other, m_pd = res["metrics"], res[other_key]["metrics"], res["equal_pandas"]["metrics"]
    stress = {
        name: {
            "covid_2020": drawdown_in(res["curves"][col].dropna(), "2020-01-01", "2020-12-31"),
            "bear_2022": drawdown_in(res["curves"][col].dropna(), "2022-01-01", "2022-12-31"),
        }
        for name, col in zip((main_key, other_key, "equal_pandas"), cols)
    }
    if alloc == "hrp":
        story_holds = bool(m_main["final_equity"] < min(m_other["final_equity"], m_pd["final_equity"])
                           and abs(m_main["max_drawdown"] - m_other["max_drawdown"]) < 0.05)
        story = "HRP under-earns equal weight in a decade the loud names won; drawdowns similar"
    else:
        story_holds = None
        story = f"n/a for --allocator {alloc}: the HRP-vs-equal story needs --allocator hrp"
    notes = {
        "fill_assumption": FILL_ASSUMPTION,
        "equity_csv": (f"columns: date, {', '.join(cols)}; the strategy's own curve first; "
                       "dollars rounded to cents; written by contracts.write_equity_csv"
                       + ("; equity_equal_engine duplicates equity_equal (same run)" if alloc == "equal" else "")),
        "fills_csv": "FILLS_SCHEMA columns, rows sorted by (ts, symbol, side, qty)",
        "positions_csv": "final PositionSnapshot incl. the account's cash, via contracts.write_positions_csv",
        "achieved_weights_csv": ("same layout as weights_csv: qty * close / equity right after each "
                                 "rebalance's fills; " + WEIGHT_TRACKING_BASIS),
    }
    summary = {
        "module": "execution",
        "versions": _versions(),
        "universe": symbols,
        "window": {"start": args.start, "end": args.end,
                   "first_bar": res["prices"].index[0].date().isoformat(),
                   "last_bar": res["prices"].index[-1].date().isoformat(),
                   "trading_days": int(len(res["prices"]))},
        "data_source": "skfolio.datasets.load_sp500_dataset (daily adjusted closes, bundled, no network)",
        "config": {"starting_cash": args.cash, "lookback_bars": args.lookback,
                   "rebalance_every": args.rebalance_every, "investment_cap": args.investment_cap,
                   "order_mode": "two_phase", "venue": DEFAULT_VENUE, "oms": "NETTING",
                   "account": "CASH", "fill_model": "default", "fees": "none",
                   "bar_volume": DEFAULT_BAR_VOLUME, "risk_checks_close_trades": True,
                   **({"fixed_weights": fixed,  # as supplied, then as traded (rescaled over the universe)
                       "fixed_weights_normalised": normalise_fixed_weights(fixed, symbols)}
                      if fixed is not None else {})},
        "fills": res["stats"]["n_fills"],
        "orders": res["stats"]["n_orders"],
        "rejections": res["stats"]["n_rejected"],
        "denied": res["stats"]["n_denied"],
        "first_fill_date": res["stats"]["first_fill_date"],
        main_key: {"metrics": m_main, "stats": _public_stats(res["stats"])},
        other_key: {"metrics": m_other, "stats": _public_stats(res[other_key]["stats"])},
        "equal_pandas": {"metrics": m_pd,
                         "daily_rebalanced_metrics": res["equal_pandas"]["daily_rebalanced_metrics"],
                         "definition": "starting_cash * (prices.loc[first_fill:] / prices.loc[first_fill]).mean(axis=1)"},
        "stress_drawdowns": stress,
        "order_sequencing_experiment": seq,
        "article": ARTICLE,
        "comparison": {
            f"{alloc}_final_equity": m_main["final_equity"],
            "equal_engine_final_equity": m_other["final_equity"],
            "equal_pandas_final_equity": m_pd["final_equity"],
            f"{alloc}_underperforms_equal_engine": m_main["final_equity"] < m_other["final_equity"],
            f"{alloc}_underperforms_equal_pandas": m_main["final_equity"] < m_pd["final_equity"],
            f"max_dd_{alloc}": m_main["max_drawdown"],
            "max_dd_equal_engine": m_other["max_drawdown"],
            "max_dd_equal_pandas": m_pd["max_drawdown"],
            "qualitative_story_holds": story_holds,
            "story": story,
        },
        "runtime_seconds": {"backtest_with_benchmarks": res["runtime_seconds"],
                            f"{alloc}_engine_run": res["stats"]["engine_run_seconds"],
                            "cli_total": time.perf_counter() - t0},
        "outputs": {k: _display_path(v) for k, v in paths.items()},
        "notes": notes,
    }
    (results / "execution_summary.json").write_text(json.dumps(_round(summary), indent=2, default=str))

    # ---- console summary
    def line(name, m, extra=""):
        return (f"  {name:<22} final ${m['final_equity']:>12,.0f}  CAGR {m['cagr']:6.2%}  "
                f"maxDD {m['max_drawdown']:6.2%}  vol {m['ann_vol']:6.2%}  Sharpe {m['sharpe']:.2f}{extra}")

    print(f"quantstack.execution  nautilus_trader {summary['versions']['nautilus_trader']}  "
          f"{len(symbols)} names {summary['window']['first_bar']}..{summary['window']['last_bar']}")
    print(f"  fills {summary['fills']} (orders {summary['orders']}, rejected {summary['rejections']}, "
          f"denied {summary['denied']}), first fill {summary['first_fill_date']}")
    print(line(f"{alloc} (engine)", m_main))
    print(line(other_key.replace("_", " "), m_other, " (same run)" if alloc == "equal" else ""))
    print(line("equal (pandas B&H)", m_pd))
    wt = res["stats"]["weight_tracking"]
    if wt["n_rebalances"]:
        print(f"  weight tracking over {wt['n_rebalances']} rebalances: mean |cap*target - achieved| "
              f"{wt['mean_abs_gap']:.4%}, max {wt['max_abs_gap']:.4%} ({wt['max_abs_gap_symbol']} "
              f"{wt['max_abs_gap_date']}), invested {wt['mean_invested_fraction']:.2%} of equity")
    for mode, v in seq.items():
        print(f"  order mode {mode:<11} orders {v['n_orders']:>4} fills {v['n_fills']:>4} "
              f"denied {v['n_denied']:>3} halted {v['halted_early']} (last day {v['last_published_day']})")
    print(f"  runtime: backtest+benchmarks {res['runtime_seconds']:.1f}s, CLI total "
          f"{summary['runtime_seconds']['cli_total']:.1f}s -> {summary['outputs']['figure']}")
    return summary


if __name__ == "__main__":
    main()
