"""Run the loop: NautilusTrader backtest of the skfolio rebalance, curve read back from the sink.

``python -m quantstack.execution.backtest [--allocator hrp] [--start 2016-01-01] [--end 2022-12-28]``

What it does
------------
1. Loads daily adjusted closes for the universe (skfolio's bundled dataset,
   see ``data.py``), builds ``Equity`` instruments (lot size 1) and one
   ``Bar`` per (symbol, day) directly (the ``BarDataWrangler`` is broken under
   pandas 3), plus one synthetic close trade per bar so the ``RiskEngine`` can
   price market orders.
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
   same names started on the HRP run's first fill date -- "the blue line that
   cannot reject a trade" (fully invested, no cash buffer, never trades).
7. Optionally reproduces the order-sequencing experiment on the full window
   (``sells_first`` and ``buys_first`` modes; see ``strategy.py``).

Version-skew notes (nautilus_trader 1.231.0 + pandas 3.0.6): ``engine.run()``
emits a ``Pandas4Warning`` (it calls the deprecated ``pd.Timestamp.utcnow``),
silenced here; Nautilus logging is initialised once per process and the first
engine's ``LoggingConfig`` wins, so the noisy order-sequencing reproduction runs
in a child interpreter with logging OFF.

Metrics are measured from the first fill date: CAGR, max drawdown,
annualised volatility (daily returns x sqrt(252)), Sharpe with rf = 0, and
turnover (one-way, annualised: 0.5 x traded notional / mean equity / years,
reported with and without the initial buy-in).

Outputs (CLI): ``results/execution_equity.csv``, ``results/execution_fills.csv``,
``results/execution_positions.csv`` (final ``PositionSnapshot`` via
``contracts.write_positions_csv``; the risk module turns this file into an ORE
portfolio), ``results/execution_summary.json``,
``results/figures/execution_equity.png``.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from quantstack.contracts import (
    FILLS_SCHEMA,
    DashboardSink,
    PositionSnapshot,
    RecordingSink,
    write_positions_csv,
)
from quantstack.execution.data import (
    DEFAULT_BAR_VOLUME,
    DEFAULT_END,
    DEFAULT_START,
    DEFAULT_SYMBOLS,
    DEFAULT_VENUE,
    interleave_trades_and_bars,
    load_prices,
    make_bar_types,
    make_bars,
    make_close_trades,
    make_instruments,
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
        return {"traded_notional": 0.0, "turnover_annual_oneway": 0.0,
                "turnover_annual_oneway_ex_initial": 0.0}
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
) -> EngineRun:
    from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.model.currencies import USD
    from nautilus_trader.model.enums import AccountType, OmsType
    from nautilus_trader.model.identifiers import TraderId, Venue
    from nautilus_trader.model.objects import Money

    from quantstack.execution.strategy import SkfolioRebalance, SkfolioRebalanceConfig

    symbols = list(prices.columns)
    instruments = make_instruments(symbols, venue_name)
    bar_types = make_bar_types(instruments)
    bars = make_bars(prices, instruments, bar_types, volume=bar_volume)
    data = interleave_trades_and_bars(bars, make_close_trades(bars, bar_volume)) if risk_checks else bars

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
        engine.add_data(data)  # sorted by ts_init (stable), trade before bar
        cfg = SkfolioRebalanceConfig(
            instrument_ids=[instruments[s].id for s in symbols],
            bar_types=[bar_types[s] for s in symbols],
            lookback_bars=lookback_bars,
            rebalance_every=rebalance_every,
            investment_cap=investment_cap,
            allocator=allocator,
            order_mode=order_mode,
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
        "weights_history": strat.weights_history,
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
    symbols: Sequence[str] = DEFAULT_SYMBOLS,
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
) -> dict:
    """Backtest ``allocator`` on ``symbols`` over [start, end]; return curves and metrics.

    Returns a dict with ``equity`` (pd.Series read back from the sink),
    ``fills`` (DataFrame, ``FILLS_SCHEMA`` columns), ``snapshot`` (final
    ``PositionSnapshot``, non-zero lines), ``metrics`` (from the first fill),
    ``stats`` (counts, runtimes, cross-checks), ``reports`` (Nautilus report
    DataFrames), ``prices``; with ``benchmarks=True`` also ``equal_engine``
    and ``equal_pandas`` sub-results and a combined ``curves`` DataFrame.
    ``sink`` receives every update live (a recorder is tee'd alongside it).
    """
    t_all = time.perf_counter()
    if prices is None:
        prices = load_prices(symbols, start, end)
    kw = dict(starting_cash=starting_cash, lookback_bars=lookback_bars,
              rebalance_every=rebalance_every, investment_cap=investment_cap,
              order_mode=order_mode, risk_checks=risk_checks, bar_volume=bar_volume,
              venue_name=venue, log_level=log_level)
    main = _engine_run(prices, allocator, sink=sink, **kw)
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
    }
    if benchmarks and first_fill is not None:
        eq_alloc = "equal" if allocator != "equal" else "hrp"
        other = _engine_run(prices, eq_alloc, sink=None, **kw)
        ew_bh = equal_weight_pandas(prices, first_fill, starting_cash)
        ew_daily = equal_weight_daily_rebalanced(prices, first_fill, starting_cash)
        other_ff = pd.Timestamp(other.stats["first_fill_date"]) if other.stats["first_fill_date"] else first_fill
        out["equal_engine" if eq_alloc == "equal" else "hrp_engine"] = {
            "equity": other.equity, "fills": other.fills, "stats": other.stats,
            "metrics": {**perf_metrics(other.equity, first_fill),
                        **turnover_stats(other.fills, other.equity, other_ff)},
        }
        out["equal_pandas"] = {
            "equity": ew_bh,
            "metrics": perf_metrics(ew_bh, first_fill),
            "daily_rebalanced_metrics": perf_metrics(ew_daily, first_fill),
        }
        name_main = f"equity_{allocator}"
        name_other = f"equity_{eq_alloc}_engine"
        out["curves"] = pd.DataFrame({
            name_main: main.equity,
            name_other: other.equity,
            "equity_equal_pandas": ew_bh,
        }).rename_axis("date")
    out["runtime_seconds"] = time.perf_counter() - t_all
    return out


# --------------------------------------------------------------------------- figure

LIGHT = {
    "surface": "#fcfcfb", "text": "#0b0b0b", "text2": "#52514e", "grid": "#e4e3df",
    "s1": "#2a78d6", "s2": "#eb6834", "s3": "#1baf7a", "shade": "#f0efec",
}


def plot_equity(curves: pd.DataFrame, first_fill: pd.Timestamp, path: Path, title_extra: str = "") -> Path:
    """Three equity curves on a log scale + an underwater (drawdown) panel."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator, PercentFormatter

    c = LIGHT
    series = [
        ("equity_equal_pandas", "Equal weight, pandas buy-and-hold", c["s1"]),
        ("equity_hrp", "HRP in NautilusTrader", c["s2"]),
        ("equity_equal_engine", "Equal weight in NautilusTrader (monthly)", c["s3"]),
    ]
    series = [s for s in series if s[0] in curves.columns]
    df = curves.loc[pd.Timestamp(first_fill) - pd.Timedelta(days=45):]

    plt.rcParams.update({"font.size": 9, "axes.edgecolor": c["text2"], "axes.labelcolor": c["text2"],
                         "xtick.color": c["text2"], "ytick.color": c["text2"]})
    fig, (ax, axd) = plt.subplots(2, 1, figsize=(9, 6.2), sharex=True,
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
    ax.set_title("Equity from first fill: HRP vs equal weight, 8 US large caps" + title_extra,
                 loc="left", fontsize=11, color=c["text"])
    axd.set_ylabel("Drawdown")
    axd.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    axd.xaxis.set_major_locator(mdates.YearLocator())
    axd.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axd.set_xlabel("Date")
    fig.subplots_adjust(left=0.1, right=0.88, top=0.93, bottom=0.08)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120, facecolor=c["surface"])
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- sequencing experiment


def sequencing_experiment(
    symbols: Sequence[str], start: str, end: str, allocator: str = "hrp",
    starting_cash: float = 1_000_000, lookback_bars: int = 252, rebalance_every: int = 21,
    investment_cap: float = 0.98, modes: Sequence[str] = ("sells_first", "buys_first"),
    log_level: str = "OFF",
) -> dict:
    """Re-run the backtest with the naive order sequencings (see ``strategy.py``)."""
    prices = load_prices(symbols, start, end)
    out = {}
    for mode in modes:
        r = run_backtest(symbols, start, end, allocator=allocator, starting_cash=starting_cash,
                         lookback_bars=lookback_bars, rebalance_every=rebalance_every,
                         investment_cap=investment_cap, order_mode=mode, benchmarks=False,
                         prices=prices, log_level=log_level)
        st = r["stats"]
        row = {k: st[k] for k in ("n_orders", "n_fills", "n_denied", "n_rejected",
                                  "halted_early", "last_published_day")}
        row["final_equity"] = float(r["equity"].iloc[-1]) if not r["equity"].empty else None
        row["rejections_sample"] = st["rejections_sample"][:2]
        out[mode] = row
    return out


def run_sequencing_experiment_subprocess(symbols, start, end, allocator, cash, lookback,
                                         rebalance_every, investment_cap) -> dict:
    """Run :func:`sequencing_experiment` in a fresh interpreter with logging OFF."""
    import subprocess

    args = json.dumps([list(symbols), start, end, allocator, cash, lookback,
                       rebalance_every, investment_cap])
    code = ("import json,sys; from quantstack.execution.backtest import sequencing_experiment as f; "
            "a=json.loads(sys.argv[1]); print('@@'+json.dumps(f(*a)))")
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
    return {k: v for k, v in stats.items() if k not in ("weights_history", "submitted")}


def main(argv: Sequence[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--allocator", default="hrp", choices=["hrp", "equal"])
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=DEFAULT_END)
    ap.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    ap.add_argument("--cash", type=float, default=1_000_000)
    ap.add_argument("--lookback", type=int, default=252)
    ap.add_argument("--rebalance-every", type=int, default=21)
    ap.add_argument("--investment-cap", type=float, default=0.98)
    ap.add_argument("--no-sequencing-experiment", action="store_true",
                    help="skip the sells_first / buys_first reproduction runs")
    ap.add_argument("--results-dir", default=str(RESULTS_DIR))
    args = ap.parse_args(argv)

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    results = Path(args.results_dir)
    figs = results / "figures"
    t0 = time.perf_counter()
    res = run_backtest(symbols, args.start, args.end, allocator=args.allocator,
                       starting_cash=args.cash, lookback_bars=args.lookback,
                       rebalance_every=args.rebalance_every, investment_cap=args.investment_cap)
    main_key, other_key = (args.allocator, "equal_engine") if args.allocator == "hrp" else ("equal", "hrp_engine")

    # ---- files
    results.mkdir(parents=True, exist_ok=True)
    curves = res["curves"].copy()
    curves.index = curves.index.strftime("%Y-%m-%d")
    curves.to_csv(results / "execution_equity.csv", float_format="%.2f")
    # exactly FILLS_SCHEMA columns: the dashboard replays this file straight into
    # a Perspective table built from that schema (an extra column would not fit)
    res["fills"][list(FILLS_SCHEMA)].to_csv(results / "execution_fills.csv", index=False,
                                            float_format="%.4f")
    write_positions_csv(res["snapshot"], results / "execution_positions.csv")
    weights = pd.DataFrame(res["stats"]["weights_history"])
    weights.to_csv(results / f"execution_weights_{args.allocator}.csv", index=False, float_format="%.6f")
    fig_path = plot_equity(res["curves"], res["first_fill"], figs / "execution_equity.png")

    # ---- order-sequencing experiment (full window, same allocator), in a child
    # process: Nautilus logging is process-global and the first engine's
    # LoggingConfig wins, so a quiet run needs its own interpreter.
    seq = {}
    if not args.no_sequencing_experiment:
        seq = run_sequencing_experiment_subprocess(
            symbols, args.start, args.end, args.allocator, args.cash, args.lookback,
            args.rebalance_every, args.investment_cap)
        st = res["stats"]
        seq["two_phase"] = {k: st[k] for k in ("n_orders", "n_fills", "n_denied", "n_rejected",
                                               "halted_early", "last_published_day")}
        seq["two_phase"]["final_equity"] = float(res["equity"].iloc[-1])

    m_main, m_other, m_pd = res["metrics"], res[other_key]["metrics"], res["equal_pandas"]["metrics"]
    hrp_m = m_main if args.allocator == "hrp" else m_other
    ew_m = m_other if args.allocator == "hrp" else m_main
    stress = {
        name: {
            "covid_2020": drawdown_in(res["curves"][col].dropna(), "2020-01-01", "2020-12-31"),
            "bear_2022": drawdown_in(res["curves"][col].dropna(), "2022-01-01", "2022-12-31"),
        }
        for name, col in (("hrp", "equity_hrp"), ("equal_engine", "equity_equal_engine"),
                          ("equal_pandas", "equity_equal_pandas"))
        if col in res["curves"].columns
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
                   "bar_volume": DEFAULT_BAR_VOLUME, "risk_checks_close_trades": True},
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
            "hrp_final_equity": hrp_m["final_equity"],
            "equal_engine_final_equity": ew_m["final_equity"],
            "equal_pandas_final_equity": m_pd["final_equity"],
            "hrp_underperforms_equal_engine": hrp_m["final_equity"] < ew_m["final_equity"],
            "hrp_underperforms_equal_pandas": hrp_m["final_equity"] < m_pd["final_equity"],
            "max_dd_hrp": hrp_m["max_drawdown"],
            "max_dd_equal_engine": ew_m["max_drawdown"],
            "max_dd_equal_pandas": m_pd["max_drawdown"],
            "qualitative_story_holds": bool(
                hrp_m["final_equity"] < min(ew_m["final_equity"], m_pd["final_equity"])
                and abs(hrp_m["max_drawdown"] - ew_m["max_drawdown"]) < 0.05
            ),
            "story": "HRP under-earns equal weight in a decade the loud names won; drawdowns similar",
        },
        "runtime_seconds": {"backtest_with_benchmarks": res["runtime_seconds"],
                            "hrp_engine_run": res["stats"]["engine_run_seconds"] if args.allocator == "hrp" else res[other_key]["stats"]["engine_run_seconds"],
                            "cli_total": time.perf_counter() - t0},
        "outputs": {
            "equity_csv": "results/execution_equity.csv",
            "fills_csv": "results/execution_fills.csv",
            "positions_csv": "results/execution_positions.csv",
            "weights_csv": f"results/execution_weights_{args.allocator}.csv",
            "figure": "results/figures/execution_equity.png",
        },
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
    print(line(f"{args.allocator} (engine)", m_main))
    print(line(other_key.replace("_", " "), m_other))
    print(line("equal (pandas B&H)", m_pd))
    for mode, v in seq.items():
        print(f"  order mode {mode:<11} orders {v['n_orders']:>4} fills {v['n_fills']:>4} "
              f"denied {v['n_denied']:>3} halted {v['halted_early']} (last day {v['last_published_day']})")
    print(f"  runtime: backtest+benchmarks {res['runtime_seconds']:.1f}s, CLI total "
          f"{summary['runtime_seconds']['cli_total']:.1f}s -> {fig_path.relative_to(REPO_ROOT) if fig_path.is_relative_to(REPO_ROOT) else fig_path}")
    return summary


if __name__ == "__main__":
    main()
