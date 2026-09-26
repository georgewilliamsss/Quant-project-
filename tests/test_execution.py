"""Tests for quantstack.execution (NautilusTrader loop + skfolio sizing + sink).

Fast tests use a short window (3 names, 2018, lookback 60, monthly rebalance)
and run several small engines in one process (~ a few seconds in total).
The full 8-name 2016-2022 run is marked ``slow``.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from quantstack.contracts import FILLS_SCHEMA, POSITIONS_SCHEMA, RecordingSink, read_positions_csv, write_positions_csv
from quantstack.execution.backtest import (
    TeeSink,
    equal_weight_pandas,
    perf_metrics,
    run_backtest,
)
from quantstack.execution.data import (
    load_prices,
    make_bar_types,
    make_bars,
    make_close_trades,
    make_instruments,
)

SYMS = ["AAPL", "MSFT", "JPM"]
START, END = "2018-01-01", "2018-12-31"
FAST = dict(lookback_bars=60, rebalance_every=21)


@pytest.fixture(scope="module")
def prices():
    return load_prices(SYMS, START, END)


@pytest.fixture(scope="module")
def short_run(prices):
    sink = RecordingSink()
    res = run_backtest(SYMS, START, END, sink=sink, prices=prices, **FAST)
    return res, sink


# ----------------------------------------------------------------------------- data


def test_load_prices_default_universe():
    p = load_prices()
    assert list(p.columns) == ["AAPL", "MSFT", "JPM", "JNJ", "XOM", "PG", "HD", "UNH"]
    assert p.index[0] == pd.Timestamp("2016-01-04") and p.index[-1] == pd.Timestamp("2022-12-28")
    assert not p.isna().any().any()


def test_make_bars_count_monotonic_and_close_only(prices):
    inst = make_instruments(SYMS)
    bts = make_bar_types(inst)
    bars = make_bars(prices, inst, bts)
    assert len(bars) == prices.shape[0] * prices.shape[1]
    ts = np.array([b.ts_init for b in bars], dtype=np.int64)
    assert (np.diff(ts) >= 0).all()
    assert all(b.ts_event == b.ts_init for b in bars)
    first = pd.Timestamp(bars[0].ts_init, unit="ns", tz="UTC")
    assert first == pd.Timestamp(prices.index[0]).tz_localize("UTC") + pd.Timedelta(hours=21)
    b = bars[0]
    assert b.open == b.high == b.low == b.close
    assert str(b.bar_type) == "AAPL.XNAS-1-DAY-LAST-EXTERNAL"
    assert abs(float(b.close) - prices["AAPL"].iloc[0]) < 0.006
    assert inst["AAPL"].lot_size.as_double() == 1.0 and inst["AAPL"].size_precision == 0
    trades = make_close_trades(bars)
    assert len(trades) == len(bars) and trades[5].price == bars[5].close


def test_bar_data_wrangler_pandas3_readonly(prices):
    """Documents the version skew: the wrangler chokes on pandas 3 read-only arrays."""
    from nautilus_trader.persistence.wranglers import BarDataWrangler

    inst = make_instruments(["AAPL"])["AAPL"]
    bt = make_bar_types({"AAPL": inst})["AAPL"]
    idx = pd.DatetimeIndex(prices.index[:5]).tz_localize("UTC") + pd.Timedelta(hours=21)
    c = prices["AAPL"].iloc[:5].to_numpy()
    df = pd.DataFrame({"open": c, "high": c, "low": c, "close": c, "volume": 1.0}, index=idx)
    try:
        BarDataWrangler(bt, inst).process(df)
    except ValueError as exc:
        assert "read-only" in str(exc)
    else:  # pragma: no cover - a future nautilus/pandas combination
        pytest.skip("BarDataWrangler works in this version combination; direct-Bar path kept anyway")


# ----------------------------------------------------------------------------- backtest


def test_backtest_runs_with_fills_and_no_rejections(short_run):
    res, _ = short_run
    st = res["stats"]
    assert st["n_fills"] > 0
    assert st["n_rejected"] == 0
    assert st["n_denied"] == 0
    assert not st["halted_early"]
    assert st["n_fills"] == st["n_orders"]  # one fill per order at the close (volume placeholder)


def test_equity_curve_length_equals_trading_days(short_run, prices):
    res, sink = short_run
    eq = res["equity"]
    assert len(eq) == len(prices)
    assert (eq.index == prices.index).all()
    # the curve is read back from the sink the caller passed in
    pd.testing.assert_series_equal(sink.equity_curve(), eq, check_names=False)
    assert eq.iloc[0] == pytest.approx(1_000_000)


def test_final_equity_in_sane_band(short_run):
    res, _ = short_run
    final = res["equity"].iloc[-1]
    assert 700_000 < final < 1_400_000
    m = res["metrics"]
    assert 0 <= m["max_drawdown"] < 0.5
    assert math.isfinite(m["sharpe"]) and 0 < m["ann_vol"] < 0.6


def test_sells_submitted_before_buys_on_every_rebalance(short_run):
    res, _ = short_run
    sub = pd.DataFrame(res["stats"]["submitted"])
    assert not sub.empty
    saw_mixed_day = False
    for _, day in sub.groupby("date", sort=False):
        sides = list(day["side"])
        if "BUY" in sides and "SELL" in sides:
            saw_mixed_day = True
        first_buy = sides.index("BUY") if "BUY" in sides else len(sides)
        assert "SELL" not in sides[first_buy:], f"a SELL was submitted after a BUY: {sides}"
    assert saw_mixed_day, "no rebalance had both sells and buys; the ordering test is vacuous"


def test_sink_rows_follow_contract_schemas(short_run):
    res, sink = short_run
    assert set(sink.positions) == set(SYMS)
    for row in sink.positions.values():
        assert set(row) == set(POSITIONS_SCHEMA)
    assert len(sink.fills) == res["stats"]["n_fills"]
    assert set(sink.fills[0]) == set(FILLS_SCHEMA)
    assert list(res["fills"].columns) == list(FILLS_SCHEMA)


def test_engine_reports_agree_with_strategy(short_run):
    st = short_run[0]["stats"]
    assert st["fills_report_rows"] == st["n_fills"]
    assert st["final_cash"] == pytest.approx(st["final_cash_engine_account"], abs=1e-6)
    assert st["max_equity_check_diff_vs_portfolio"] < 1e-4
    assert st["final_cash"] > 0


def test_positions_csv_roundtrip(short_run, prices, tmp_path):
    snap = short_run[0]["snapshot"]
    assert snap is not None and snap.positions
    assert snap.as_of == prices.index[-1].date()
    path = write_positions_csv(snap, tmp_path / "execution_positions.csv")
    back = read_positions_csv(path)
    assert back.as_of == snap.as_of
    assert [(p.symbol, p.qty, round(p.last, 2)) for p in back.positions] == [
        (p.symbol, p.qty, round(p.last, 2)) for p in snap.positions
    ]
    # snapshot equity equals the last point of the curve read from the sink
    assert snap.equity == pytest.approx(short_run[0]["equity"].iloc[-1], rel=1e-9)


def test_equity_matches_independent_reconstruction_from_fills(short_run, prices):
    """Rebuild cash + positions from the fills with pandas and mark at the closes:
    must reproduce the curve the strategy pushed to the sink (checks the cash
    account bookkeeping, same-close fills of the two-phase buys, and the
    end-of-day publish timing)."""
    res, _ = short_run
    f = res["fills"].copy()
    f["date"] = pd.to_datetime(f["ts"]).dt.tz_convert(None).dt.normalize()
    f["signed"] = np.where(f["side"] == "BUY", f["qty"], -f["qty"])
    pos = (f.pivot_table(index="date", columns="symbol", values="signed", aggfunc="sum")
             .reindex(prices.index).fillna(0.0).cumsum().reindex(columns=SYMS, fill_value=0.0))
    cash = 1_000_000 - (f["signed"] * f["price"]).groupby(f["date"]).sum().reindex(prices.index).fillna(0.0).cumsum()
    # mark at the prices the engine saw: the bar closes at instrument precision
    inst = make_instruments(SYMS)
    bars = make_bars(prices, inst, make_bar_types(inst))
    marks = pd.DataFrame(np.array([float(b.close) for b in bars]).reshape(prices.shape),
                         index=prices.index, columns=prices.columns)
    rebuilt = cash + (pos * marks).sum(axis=1)
    np.testing.assert_allclose(res["equity"].to_numpy(), rebuilt.to_numpy(), rtol=0, atol=1e-4)


def test_benchmarks_present_and_aligned(short_run, prices):
    res, _ = short_run
    curves = res["curves"]
    assert list(curves.columns) == ["equity_hrp", "equity_equal_engine", "equity_equal_pandas"]
    assert len(curves) == len(prices)
    w = pd.DataFrame(res["equal_engine"]["stats"]["weights_history"]).set_index("date")
    assert np.allclose(w.to_numpy(), 1 / 3)
    ff = res["first_fill"]
    assert curves["equity_equal_pandas"].loc[ff] == pytest.approx(1_000_000)
    assert (curves["equity_equal_pandas"].loc[:ff] == 1_000_000).all()


def test_buys_first_is_denied_or_halts(prices):
    """The failure mode the two-phase sequencing exists to avoid."""
    res = run_backtest(SYMS, START, END, prices=prices, order_mode="buys_first",
                       benchmarks=False, **FAST)
    st = res["stats"]
    assert st["n_denied"] > 0 or st["halted_early"]


def test_tee_sink_forwards_everything():
    a, b = RecordingSink(), RecordingSink()
    t = TeeSink(a, b)
    t.update_equity(iter([{"date": "2020-01-02", "equity": 1.0}]))
    t.update_positions(iter([{"symbol": "X", "qty": 1.0, "last": 2.0, "value": 2.0}]))
    t.update_fills(iter([{"ts": "t", "symbol": "X", "side": "BUY", "qty": 1.0, "price": 2.0}]))
    for s in (a, b):
        assert s.equity == {"2020-01-02": 1.0} and "X" in s.positions and len(s.fills) == 1


def test_perf_metrics_on_synthetic_curve():
    idx = pd.bdate_range("2020-01-01", periods=4)
    eq = pd.Series([100.0, 120.0, 90.0, 110.0], index=idx)
    m = perf_metrics(eq)
    assert m["max_drawdown"] == pytest.approx(0.25)
    assert m["max_drawdown_peak"] == idx[1].date().isoformat()
    assert m["total_return"] == pytest.approx(0.10)
    p = pd.DataFrame({"A": [1.0, 2.0, 2.0], "B": [1.0, 1.0, 0.5]}, index=idx[:3])
    ew = equal_weight_pandas(p, idx[1], 100.0)
    assert ew.iloc[0] == 100.0 and ew.iloc[1] == 100.0 and ew.iloc[2] == pytest.approx(75.0)


# ----------------------------------------------------------------------------- slow


@pytest.mark.slow
def test_full_backtest_default_universe():
    res = run_backtest()  # 8 names, 2016-01-01..2022-12-28, HRP + benchmarks
    st = res["stats"]
    assert st["n_rejected"] == 0 and st["n_denied"] == 0 and not st["halted_early"]
    assert st["n_fills"] > 400
    assert st["first_fill_date"].startswith("2016-12")
    assert len(res["equity"]) == len(res["prices"])
    hrp, ew = res["metrics"], res["equal_engine"]["metrics"]
    # the article's qualitative story: HRP under-earns equal weight, similar drawdowns
    assert hrp["final_equity"] < ew["final_equity"]
    assert abs(hrp["max_drawdown"] - ew["max_drawdown"]) < 0.10
    assert res["runtime_seconds"] < 120
