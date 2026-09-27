"""Tests for quantstack.execution (NautilusTrader loop + skfolio sizing + sink).

Fast tests use a short window (3 names, 2018, lookback 60, monthly rebalance)
and run several small engines in one process (~ a few seconds in total).
The full 8-name 2016-2022 run is marked ``slow``.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from quantstack.contracts import (
    FILLS_SCHEMA,
    POSITIONS_SCHEMA,
    RecordingSink,
    equity_csv_columns,
    read_equity_csv,
    read_positions_csv,
    write_positions_csv,
)
from quantstack.execution import backtest as bt_mod
from quantstack.execution.backtest import (
    TeeSink,
    check_window,
    equal_weight_pandas,
    equity_columns,
    parse_fixed_weights,
    perf_metrics,
    plot_equity,
    run_backtest,
    sort_fills,
    weight_tracking,
    write_results,
)
from quantstack.execution.data import (
    DEFAULT_SYMBOLS,
    load_prices,
    make_bar_types,
    make_bars,
    make_close_trades,
    make_equity,
    make_instruments,
    price_precision_for,
    price_precisions,
    validate_symbols,
)
from quantstack.execution.strategy import window_returns

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


def test_engine_reports_agree_with_strategy(short_run, prices):
    st = short_run[0]["stats"]
    assert st["fills_report_rows"] == st["n_fills"]
    assert st["final_cash"] == pytest.approx(st["final_cash_engine_account"], abs=1e-6)
    # the Portfolio.equity cross-check really ran (once per completed day), not just "no diff"
    assert st["n_equity_checks"] == len(prices) > 0
    assert st["max_equity_check_diff_vs_portfolio"] < 1e-4
    assert st["final_cash"] > 0


def test_positions_csv_roundtrip(short_run, prices, tmp_path):
    snap = short_run[0]["snapshot"]
    assert snap is not None and snap.positions
    assert snap.as_of == prices.index[-1].date()
    # the final snapshot carries the account's final cash (persisted by the contract)
    assert snap.cash == pytest.approx(short_run[0]["stats"]["final_cash_engine_account"], abs=1e-6)
    assert snap.cash > 0
    path = write_positions_csv(snap, tmp_path / "execution_positions.csv")
    back = read_positions_csv(path)
    assert back.as_of == snap.as_of
    assert back.cash == pytest.approx(snap.cash, abs=1e-9)
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
    assert list(curves.columns) == equity_columns("hrp")
    assert len(curves) == len(prices)
    w = pd.DataFrame(res["equal_engine"]["stats"]["weights_history"]).set_index("date")
    assert np.allclose(w.to_numpy(), 1 / 3)
    ff = res["first_fill"]
    assert curves["equity_equal_pandas"].loc[ff] == pytest.approx(1_000_000)
    assert (curves["equity_equal_pandas"].loc[:ff] == 1_000_000).all()


def test_write_results_files_follow_the_contracts(short_run, tmp_path):
    res, _ = short_run
    paths = write_results(res, tmp_path)
    assert set(paths) == {"equity_csv", "fills_csv", "positions_csv", "weights_csv", "achieved_weights_csv"}
    # targets keep their layout; the achieved weights sit in a companion file with the same columns
    targets, achieved = pd.read_csv(paths["weights_csv"]), pd.read_csv(paths["achieved_weights_csv"])
    assert paths["achieved_weights_csv"].name == "execution_weights_hrp_achieved.csv"
    assert list(targets.columns) == list(achieved.columns) == ["date", *SYMS]
    assert list(achieved["date"]) == list(targets["date"]) and len(targets) == res["stats"]["n_rebalances"]
    assert ((achieved[SYMS] >= 0) & (achieved[SYMS] <= targets[SYMS] * 0.98 + 1e-6)).all().all()
    # equity: contracts.write_equity_csv layout, strategy first, read back by the contract reader
    eq_path = paths["equity_csv"]
    assert eq_path.read_text().splitlines()[0] == "date,equity_hrp,equity_equal_engine,equity_equal_pandas"
    assert equity_csv_columns(eq_path) == equity_columns("hrp")
    strategy = read_equity_csv(eq_path)  # default: the first equity* column
    assert strategy.name == "equity_hrp"
    np.testing.assert_allclose(strategy.to_numpy(), res["equity"].to_numpy(), rtol=0, atol=0.005)
    assert (strategy.index == res["equity"].index).all()
    bench = read_equity_csv(eq_path, "equity_equal_pandas")
    np.testing.assert_allclose(bench.to_numpy(), res["curves"]["equity_equal_pandas"].to_numpy(),
                               rtol=0, atol=0.005)
    # fills: FILLS_SCHEMA columns, same rows as the run, sorted by (ts, symbol, side, qty)
    f = pd.read_csv(paths["fills_csv"])
    assert list(f.columns) == list(FILLS_SCHEMA)
    keys = list(zip(f["ts"], f["symbol"], f["side"], f["qty"]))
    assert keys == sorted(keys) and len(f) == res["stats"]["n_fills"]
    pd.testing.assert_frame_equal(f, sort_fills(res["fills"]).round(4), check_dtype=False)
    # positions: the account's cash travels with the book
    back = read_positions_csv(paths["positions_csv"])
    assert back.cash == pytest.approx(res["snapshot"].cash, abs=1e-9)
    assert back.equity == pytest.approx(res["equity"].iloc[-1], rel=1e-9)


def test_equal_allocator_layout_duplicates_engine_benchmark(prices, tmp_path):
    res = run_backtest(SYMS, START, END, allocator="equal", prices=prices, **FAST)
    curves = res["curves"]
    assert list(curves.columns) == equity_columns("equal") == [
        "equity_equal", "equity_equal_engine", "equity_equal_pandas"]
    # the strategy *is* the equal-weight engine run: the benchmark column is a copy, not a rerun
    pd.testing.assert_series_equal(curves["equity_equal_engine"], curves["equity_equal"], check_names=False)
    assert res["equal_engine"]["stats"] is res["stats"]
    path = write_results(res, tmp_path)["equity_csv"]
    assert equity_csv_columns(path) == equity_columns("equal")
    assert read_equity_csv(path).name == "equity_equal"
    assert (tmp_path / "execution_weights_equal.csv").exists()


def test_window_too_short_returns_same_keys_with_no_fills(prices, short_run):
    short = prices.loc["2018-10-01":]
    assert len(short) <= 252
    with pytest.raises(ValueError, match="lookback_bars=252"):
        check_window(short, 252)
    check_window(prices, FAST["lookback_bars"])  # the fast window is long enough
    res = run_backtest(SYMS, prices=short)  # default lookback 252: never warms up
    assert set(res) == set(short_run[0])
    assert res["stats"]["n_fills"] == 0 and res["fills"].empty
    assert list(res["fills"].columns) == list(FILLS_SCHEMA)
    assert res["first_fill"] is None and res["stats"]["first_fill_date"] is None
    assert res["curves"].empty and list(res["curves"].columns) == equity_columns("hrp")
    assert res["equal_engine"] is None and res["equal_pandas"] is None
    assert set(res["metrics"]) == set(short_run[0]["metrics"])
    assert res["metrics"]["traded_notional"] == 0.0
    assert len(res["equity"]) == len(short) and (res["equity"] == 1_000_000).all()
    assert res["snapshot"].positions == [] and res["snapshot"].cash == pytest.approx(1_000_000)


@pytest.mark.parametrize(
    "symbols, match",
    [(["AAPL"], "at least 2"), (["AAPL", "aapl"], "duplicate"), (["AAPL", "NOPE"], "NOPE"),
     ("AAPL", "not the string")],
)
def test_invalid_universe_raises_before_the_engine(monkeypatch, symbols, match):
    def boom(*a, **k):  # pragma: no cover - reaching it is the failure
        raise AssertionError("engine started before the inputs were validated")

    monkeypatch.setattr(bt_mod, "_engine_run", boom)
    with pytest.raises(ValueError, match=match):
        run_backtest(symbols, START, END, **FAST)


def test_invalid_allocator_and_prices_columns_raise_before_the_engine(monkeypatch, prices):
    monkeypatch.setattr(bt_mod, "_engine_run", lambda *a, **k: pytest.fail("engine started"))
    with pytest.raises(ValueError, match="allocator"):
        run_backtest(SYMS, START, END, allocator="minvar", prices=prices, **FAST)
    with pytest.raises(ValueError, match="at least 2"):
        run_backtest(prices=prices[["AAPL"]], **FAST)
    assert validate_symbols([" aapl", "msft "]) == ["AAPL", "MSFT"]


@pytest.mark.parametrize(
    "argv, message",
    [(["--start", "2022-06-01"], "more than lookback_bars=252"),
     (["--symbols", "AAPL"], "at least 2"),
     (["--symbols", "AAPL,AAPL"], "duplicate"),
     (["--symbols", "AAPL,NOPE"], "NOPE"),
     (["--allocator", "fixed"], "--allocator fixed needs --fixed-weights"),
     (["--fixed-weights", "AAPL=0.5,MSFT=0.5"], "only used with --allocator fixed, not hrp"),
     (["--allocator", "equal", "--fixed-weights", "AAPL=1,MSFT=1"], "only used with --allocator fixed"),
     (["--allocator", "fixed", "--fixed-weights", "AAPL"], "expected SYM=WEIGHT"),
     (["--allocator", "fixed", "--fixed-weights", "AAPL=-1,MSFT=2"], "must be finite and >= 0"),
     (["--allocator", "fixed", "--fixed-weights", "AAPL=1,MSFT=1", "--symbols", "AAPL,MSFT,JPM"],
      "no weight for ['JPM']"),
     (["--allocator", "fixed", "--fixed-weights", "AAPL=1,MSFT=1,JPM=1", "--symbols", "AAPL,MSFT"],
      "weights for ['JPM'], which are not in the universe"),
     (["--allocator", "fixed", "--fixed-weights", "AAPL=1,NOPE=1"], "NOPE")],
)
def test_cli_rejects_bad_inputs_with_exit_code_2(tmp_path, capsys, argv, message):
    out = tmp_path / "results"
    with pytest.raises(SystemExit) as exc:
        bt_mod.main([*argv, "--no-sequencing-experiment", "--results-dir", str(out)])
    assert exc.value.code == 2
    assert message in capsys.readouterr().err
    assert not out.exists()  # nothing written


def test_plot_equity_leaves_global_matplotlib_state_alone(short_run, tmp_path):
    import matplotlib

    before_rc, before_backend = dict(matplotlib.rcParams), matplotlib.get_backend()
    res, _ = short_run
    path = plot_equity(res["curves"], res["first_fill"], tmp_path / "fig.png")
    assert path.stat().st_size > 10_000
    assert dict(matplotlib.rcParams) == before_rc
    assert matplotlib.get_backend() == before_backend


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


# ----------------------------------------------------------------------------- fixed weights

FIXED_SYMS = ["AAA", "BBB", "CCC", "DDD"]
FIXED_W = {"AAA": 0.4, "BBB": 0.3, "CCC": 0.2, "DDD": 0.1}


@pytest.fixture(scope="module")
def synthetic_prices():
    """Four seeded geometric random walks from $100 over 180 business days."""
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2019-01-01", periods=180, name="Date")
    rets = rng.normal(0.0003, 0.012, size=(len(idx), len(FIXED_SYMS)))
    return pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)), index=idx, columns=FIXED_SYMS)


@pytest.fixture(scope="module")
def fixed_run(synthetic_prices):
    return run_backtest(prices=synthetic_prices, allocator="fixed", fixed_weights=FIXED_W,
                        lookback_bars=20, rebalance_every=21)


def _strategy(allocator, fixed_weights, symbols=FIXED_SYMS):
    """A ``SkfolioRebalance`` built by hand (no engine): its own checks and ``compute_weights``."""
    from quantstack.execution.strategy import SkfolioRebalance, SkfolioRebalanceConfig

    inst = make_instruments(symbols)
    bts = make_bar_types(inst)
    cfg = SkfolioRebalanceConfig(instrument_ids=[inst[s].id for s in symbols],
                                 bar_types=[bts[s] for s in symbols],
                                 allocator=allocator, fixed_weights=fixed_weights)
    return SkfolioRebalance(cfg)


def test_fixed_allocator_rebalances_to_the_supplied_weights(fixed_run, tmp_path):
    res = fixed_run
    st = res["stats"]
    assert st["allocator"] == "fixed"
    assert st["n_fills"] > 0 and st["n_fills"] == st["n_orders"]
    assert st["n_denied"] == 0 and st["n_rejected"] == 0 and not st["halted_early"]
    assert st["n_rebalances"] >= 5
    assert st["fixed_weights_normalised"] == pytest.approx(FIXED_W, abs=1e-12)
    assert res["equal_engine"]["stats"]["fixed_weights_normalised"] is None
    # the weights file: one row per rebalance, each row the supplied vector
    paths = write_results(res, tmp_path)
    assert paths["weights_csv"] == tmp_path / "execution_weights_fixed.csv"
    w = pd.read_csv(paths["weights_csv"])
    assert list(w.columns) == ["date", *FIXED_SYMS] and len(w) == st["n_rebalances"]
    np.testing.assert_allclose(w[FIXED_SYMS].to_numpy(),
                               np.tile([FIXED_W[s] for s in FIXED_SYMS], (len(w), 1)), rtol=0, atol=1e-6)
    # ... and traded: the first rebalance buys investment_cap * w of the $1M, to within one share
    f = res["fills"]
    day0 = f[f["ts"].str[:10] == st["first_fill_date"]]
    assert set(day0["side"]) == {"BUY"} and set(day0["symbol"]) == set(FIXED_SYMS)
    for _, row in day0.iterrows():
        shortfall = 0.98 * FIXED_W[row["symbol"]] * 1_000_000 - row["qty"] * row["price"]
        assert -1e-6 <= shortfall < row["price"]
    # layout follows the <allocator> convention; the 1/N benchmark never sees the fixed vector
    assert list(res["curves"].columns) == equity_columns("fixed") == [
        "equity_fixed", "equity_equal_engine", "equity_equal_pandas"]
    assert read_equity_csv(paths["equity_csv"]).name == "equity_fixed"
    bench = pd.DataFrame(res["equal_engine"]["stats"]["weights_history"]).set_index("date")
    assert res["equal_engine"]["stats"]["allocator"] == "equal" and np.allclose(bench.to_numpy(), 0.25)


@pytest.mark.parametrize(
    "weights, expected",
    [({"AAA": 40, "BBB": 30, "CCC": 20, "DDD": 10}, [0.4, 0.3, 0.2, 0.1]),       # percentages
     ({"AAA": 0.2, "BBB": 0.1, "CCC": 0.1, "DDD": 0.0}, [0.5, 0.25, 0.25, 0.0]),  # under 1, a zero
     ({"DDD": 1, "CCC": 1, "BBB": 1, "AAA": 1}, [0.25] * 4)],                    # key order is free
)
def test_fixed_weights_are_rescaled_to_sum_to_one(weights, expected):
    """Documented behaviour: fixed weights are relative, rescaled over the universe (never rejected
    for their sum); the investment cap then applies as for HRP and 1/N."""
    returns = pd.DataFrame(np.zeros((5, len(FIXED_SYMS))), columns=FIXED_SYMS)
    w = _strategy("fixed", weights).compute_weights(returns)
    assert list(w) == FIXED_SYMS
    assert [w[s] for s in FIXED_SYMS] == pytest.approx(expected, abs=1e-12)
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize(
    "allocator, weights, match",
    [("fixed", None, "needs fixed_weights"),
     ("fixed", {}, "needs fixed_weights"),
     ("equal", FIXED_W, "only used with allocator='fixed'"),
     ("hrp", FIXED_W, "only used with allocator='fixed'"),
     ("fixed", {**FIXED_W, "AAA": -0.1}, "finite and >= 0"),
     ("fixed", {**FIXED_W, "AAA": float("nan")}, "finite and >= 0"),
     ("fixed", {**FIXED_W, "AAA": float("inf")}, "finite and >= 0"),
     ("fixed", {**FIXED_W, "AAA": "heavy"}, "not a number"),
     ("fixed", {"AAA": 0.5, "BBB": 0.5}, r"no weight for \['CCC', 'DDD'\]"),
     # a weight for a name that is not traded is refused, not dropped with the rest rescaled
     ("fixed", {**FIXED_W, "ZZZ": 4}, r"weights for \['ZZZ'\], which are not in the universe"),
     ("fixed", {"AAA": 1, "BBB": 1, "CCC": 1, "ZZZ": 1},
      r"no weight for \['DDD'\].*; weights for \['ZZZ'\], which are not in the universe"),
     ("fixed", dict.fromkeys(FIXED_SYMS, 0.0), "positive total")],
)
def test_fixed_weights_checked_before_the_engine_and_by_the_strategy(
        monkeypatch, synthetic_prices, allocator, weights, match):
    monkeypatch.setattr(bt_mod, "_engine_run", lambda *a, **k: pytest.fail("engine started"))
    with pytest.raises(ValueError, match=match):
        run_backtest(prices=synthetic_prices, allocator=allocator, fixed_weights=weights, **FAST)
    with pytest.raises(ValueError, match=match):  # the strategy enforces the same contract itself
        _strategy(allocator, weights)


def test_parse_fixed_weights_inline_json_and_csv(tmp_path):
    expected = {"AAPL": 0.25, "MSFT": 0.75}
    assert parse_fixed_weights("AAPL=0.25,MSFT=0.75") == expected
    assert parse_fixed_weights(" aapl = 0.25 , msft=0.75, ") == expected  # normalised like --symbols
    (tmp_path / "w.json").write_text('{"AAPL": 0.25, "msft": 0.75}')
    assert parse_fixed_weights(str(tmp_path / "w.json")) == expected
    (tmp_path / "w.csv").write_text("Symbol, Weight ,note\nAAPL,0.25,core\nMSFT,0.75,\n")
    assert parse_fixed_weights(str(tmp_path / "w.csv")) == expected
    (tmp_path / "W.JSON").write_text('{"AAPL": 1, "MSFT": 3}')  # ints; suffix case-insensitive
    assert parse_fixed_weights(str(tmp_path / "W.JSON")) == {"AAPL": 1.0, "MSFT": 3.0}
    assert list(parse_fixed_weights("MSFT=1,AAPL=3")) == ["MSFT", "AAPL"]  # order kept (default universe)


@pytest.mark.parametrize(
    "spec, files, match",
    [("AAPL", {}, "expected SYM=WEIGHT"),
     ("AAPL=x", {}, "not a number"),
     ("AAPL=1,aapl=2", {}, "duplicate symbol AAPL"),
     (" , ", {}, "no SYM=WEIGHT"),
     ("=0.5", {}, "empty symbol"),
     ("missing.json", {}, "not found"),
     ("w.json", {"w.json": '[["AAPL", 1]]'}, "one JSON object"),
     ("w.json", {"w.json": "{AAPL: 1}"}, "not valid JSON"),
     ("w.json", {"w.json": '{"AAPL": true}'}, "not a number"),
     ("w.json", {"w.json": '{"AAPL": 0.9, "MSFT": 0.1, "AAPL": 0.1}'}, "duplicate symbol AAPL"),  # not last-wins
     ("w.json", {"w.json": '{"AAPL": 0.5, "aapl": 0.5}'}, "duplicate symbol AAPL"),
     ("w.csv", {"w.csv": "ticker,w\nAAPL,1\n"}, "symbol,weight"),
     ("w.csv", {"w.csv": "symbol,weight\nAAPL,\n"}, "not a number")],
)
def test_parse_fixed_weights_rejects_bad_specs(tmp_path, monkeypatch, spec, files, match):
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    monkeypatch.chdir(tmp_path)  # relative file specs resolve here
    with pytest.raises(ValueError, match=match):
        parse_fixed_weights(spec)


def test_parse_fixed_weights_reads_utf8_bom_files(tmp_path):
    """Excel's "CSV UTF-8" export starts the file with a byte-order mark (and uses CRLF)."""
    (tmp_path / "w.csv").write_bytes("Symbol,Weight\r\nAAPL,0.25\r\nMSFT,0.75\r\n".encode("utf-8-sig"))
    (tmp_path / "w.json").write_bytes('{"AAPL": 0.25, "MSFT": 0.75}'.encode("utf-8-sig"))
    for name in ("w.csv", "w.json"):
        assert (tmp_path / name).read_bytes().startswith(b"\xef\xbb\xbf")
        assert parse_fixed_weights(str(tmp_path / name)) == {"AAPL": 0.25, "MSFT": 0.75}


def test_run_backtest_symbols_must_match_the_price_columns(monkeypatch, synthetic_prices):
    class Reached(Exception):
        pass

    def reached(*a, **k):
        raise Reached

    monkeypatch.setattr(bt_mod, "_engine_run", reached)
    with pytest.raises(ValueError, match=r"in symbols only \['AAPL', 'MSFT'\], in prices.columns only "
                                         r"\['AAA', 'BBB', 'CCC', 'DDD'\]"):
        run_backtest(list(DEFAULT_SYMBOLS[:2]), prices=synthetic_prices, **FAST)
    with pytest.raises(ValueError, match=r"in symbols only \[\], in prices.columns only \['DDD'\]"):
        run_backtest(["AAA", "BBB", "CCC"], prices=synthetic_prices, **FAST)
    # the same names (any order, any case) or no symbols at all: validation passes, the engine is reached
    for symbols in (None, ["ddd", "CCC", " bbb", "AAA"]):
        with pytest.raises(Reached):
            run_backtest(symbols, prices=synthetic_prices, **FAST)


def test_cli_fixed_allocator_end_to_end(tmp_path):
    """--fixed-weights from a CSV of percentages; --symbols defaults to its symbols."""
    out = tmp_path / "results"
    (tmp_path / "mine.csv").write_text("symbol,weight\nAAPL,50\nMSFT,30\nJPM,20\n")
    bt_mod.main(["--allocator", "fixed", "--fixed-weights", str(tmp_path / "mine.csv"),
                 "--start", START, "--end", END, "--lookback", "60", "--no-sequencing-experiment",
                 "--results-dir", str(out)])
    summary = json.loads((out / "execution_summary.json").read_text())
    assert summary["universe"] == SYMS
    assert summary["config"]["fixed_weights"] == {"AAPL": 50.0, "MSFT": 30.0, "JPM": 20.0}
    assert summary["config"]["fixed_weights_normalised"] == pytest.approx({"AAPL": 0.5, "MSFT": 0.3, "JPM": 0.2})
    assert summary["fixed"]["stats"]["allocator"] == "fixed"
    assert summary["fills"] > 0 and summary["denied"] == 0 and summary["rejections"] == 0
    assert summary["outputs"]["weights_csv"].endswith("execution_weights_fixed.csv")
    assert summary["outputs"]["achieved_weights_csv"].endswith("execution_weights_fixed_achieved.csv")
    stats = summary["fixed"]["stats"]
    assert "achieved_weights_history" not in stats and "weights_history" not in stats
    assert stats["weight_tracking"]["n_rebalances"] == stats["n_rebalances"] > 0
    assert stats["price_precision"] == dict.fromkeys(SYMS, 2)
    assert stats["fixed_weights_normalised"] == pytest.approx({"AAPL": 0.5, "MSFT": 0.3, "JPM": 0.2})
    assert equity_csv_columns(out / "execution_equity.csv") == equity_columns("fixed")
    w = pd.read_csv(out / "execution_weights_fixed.csv")
    np.testing.assert_allclose(w[SYMS].to_numpy(), np.tile([0.5, 0.3, 0.2], (len(w), 1)), rtol=0, atol=1e-6)


# ----------------------------------------------------------------------------- price precision

MIXED_SYMS = ["PENNY", "BIG", "MIDA", "MIDB"]
MIXED_FIXED = {"PENNY": 0.25, "BIG": 0.005, "MIDA": 0.37, "MIDB": 0.375}
MIXED_CASH = 200_000


@pytest.fixture(scope="module")
def mixed_prices():
    """NaN-free panel: one name around 0.005 (half a penny), one around 400, two ordinary ones."""
    rng = np.random.default_rng(11)
    idx = pd.bdate_range("2019-01-01", periods=100, name="Date")
    rets = rng.normal(0.0, 0.02, size=(len(idx), len(MIXED_SYMS)))
    return pd.DataFrame(np.array([0.005, 400.0, 50.0, 80.0]) * np.exp(np.cumsum(rets, axis=0)),
                        index=idx, columns=MIXED_SYMS)


@pytest.fixture(scope="module")
def mixed_runs(mixed_prices):
    return {alloc: run_backtest(prices=mixed_prices, allocator=alloc, starting_cash=MIXED_CASH,
                                fixed_weights=MIXED_FIXED if alloc == "fixed" else None,
                                lookback_bars=20, rebalance_every=21, benchmarks=False)
            for alloc in ("fixed", "equal", "hrp")}


@pytest.mark.parametrize(
    "closes, expected",
    [([20.854, 300.0], 2), ([1.80, 5.0], 2), ([1.0], 2), ([0.5], 4), ([0.0104, 0.4], 5), ([0.005], 6),
     ([0.000793, 0.0095], 7), ([1e-12], 9), ([np.nan, 0.004, 3.0], 6), ([np.nan, 0.0, -1.0], 2), ([], 2)],
)
def test_price_precision_rule(closes, expected):
    """2 when every close is >= 1, else >= 4 significant digits at the smallest close, capped at 9."""
    assert price_precision_for(closes) == expected


def test_price_precision_is_2_for_every_skfolio_name():
    """The bundled dataset (and so the pinned figures of the slow test) keeps the 0.01 tick."""
    from skfolio.datasets import load_sp500_dataset

    df = load_sp500_dataset()
    assert set(price_precisions(df.loc[pd.Timestamp("2016-01-01"):]).values()) == {2}
    assert set(price_precisions(load_prices()).values()) == {2}


@pytest.mark.parametrize("precision", [6, 7, 8, 9])
def test_equity_instrument_works_at_fine_precision(precision):
    from nautilus_trader.model.objects import Price

    inst = make_equity("PENNY", price_precision=precision)
    assert inst.price_precision == precision
    assert inst.price_increment == Price.from_str(f"{10.0 ** -precision:.{precision}f}")
    px = inst.make_price(0.0001234567891)
    assert px.precision == precision and float(px) == pytest.approx(0.0001234567891, abs=10.0 ** -precision)
    assert Price.from_str(str(px)) == px
    with pytest.raises(ValueError, match="price_precision"):
        make_equity("PENNY", price_precision=precision + 10)


def test_bars_keep_sub_penny_closes_at_the_derived_precision(mixed_prices):
    prec = price_precisions(mixed_prices)
    assert prec == {"PENNY": 6, "BIG": 2, "MIDA": 2, "MIDB": 2}
    inst = make_instruments(MIXED_SYMS, price_precision=prec)
    bars = make_bars(mixed_prices, inst, make_bar_types(inst))
    closes = np.array([float(b.close) for b in bars]).reshape(mixed_prices.shape)
    assert len(bars) == mixed_prices.size and (closes > 0).all()  # no bar close is 0
    half_tick = np.array([0.5 * 10.0 ** -prec[s] for s in MIXED_SYMS])
    assert (np.abs(closes - mixed_prices.to_numpy()) <= half_tick + 1e-12).all()
    rel = np.abs(closes[:, 0] / mixed_prices["PENNY"].to_numpy() - 1)
    assert rel.max() < 5e-4  # >= 4 significant digits (a 0.01 tick was off by up to 100%)


def test_make_bars_refuses_a_close_that_rounds_to_zero(mixed_prices):
    # the old fixed 0.01 tick: the half-penny name rounds to 0.00 on its first close under 0.005
    inst = make_instruments(MIXED_SYMS)
    first_zero = mixed_prices.index[(mixed_prices["PENNY"] < 0.005).to_numpy()][0].date()
    with pytest.raises(ValueError, match=rf"PENNY: close .* on {first_zero} rounds to 0\.00 at the "
                                         r"instrument's price_precision 2"):
        make_bars(mixed_prices, inst, make_bar_types(inst))
    bad = mixed_prices.copy()
    bad.iloc[7, 2] = 0.0
    inst = make_instruments(MIXED_SYMS, price_precision=price_precisions(bad))
    with pytest.raises(ValueError, match=rf"MIDA: close 0\.0 on {bad.index[7].date()} is not a positive"):
        make_bars(bad, inst, make_bar_types(inst))


def test_backtest_refuses_a_close_below_the_finest_tick(monkeypatch, mixed_prices):
    """Even the derived precision is capped (9): a close under half a nano-unit would be marked at 0."""
    bad = mixed_prices.copy()
    bad.iloc[10, 0] = 1e-10
    assert price_precisions(bad)["PENNY"] == 9
    with pytest.raises(ValueError, match=rf"PENNY: close 1e-10 on {bad.index[10].date()} rounds to "
                                         r"0\.000000000 at the instrument's price_precision 9"):
        run_backtest(prices=bad, allocator="equal", lookback_bars=20, benchmarks=False)


def test_window_returns_refuses_non_finite_returns():
    p = pd.DataFrame({"A": [1.0, 1.1, 1.21, 1.1], "B": [2.0, 0.0, 0.0, 2.0], "C": [3.0, 3.3, np.inf, 3.0]})
    ok = window_returns(p[["A"]])
    pd.testing.assert_frame_equal(ok, p[["A"]].pct_change().dropna())
    # B: -100% then 0/0 = NaN then 2/0 = inf; C: an inf close -> inf (then 3/inf - 1 = -1)
    with pytest.raises(ValueError, match=r"rebalance 2020-01-02: non-finite returns in the 4-bar price window "
                                         r"for B \(2 of 3\), C \(1 of 3\)"):
        window_returns(p, label="rebalance 2020-01-02")
    with pytest.raises(ValueError, match="non-finite returns"):
        window_returns(p[["A"]].iloc[:1])  # no return at all


@pytest.mark.parametrize("allocator", ["fixed", "equal", "hrp"])
def test_sub_penny_and_high_priced_names_trade_under_every_allocator(mixed_runs, mixed_prices, allocator):
    res = mixed_runs[allocator]
    st = res["stats"]
    assert st["price_precision"] == {"PENNY": 6, "BIG": 2, "MIDA": 2, "MIDB": 2}
    assert st["n_fills"] == st["n_orders"] > 0 and st["n_denied"] == 0 and st["n_rejected"] == 0
    assert not st["halted_early"] and st["n_rebalances"] >= 3
    assert st["close_rounding_max_rel_error"]["PENNY"] < 5e-4
    # cash-account bookkeeping still agrees (USD money is in cents: < 1 cent per position)
    assert st["final_cash"] == pytest.approx(st["final_cash_engine_account"], abs=1e-6)
    assert st["max_equity_check_diff_vs_portfolio"] < 0.01 * len(MIXED_SYMS)
    # the half-penny name is traded at its own close, not at 0.00 / 0.01
    f = res["fills"]
    pen = f[f["symbol"] == "PENNY"]
    assert not pen.empty
    closes = mixed_prices["PENNY"].copy()
    closes.index = closes.index.strftime("%Y-%m-%d")
    np.testing.assert_allclose(pen["price"].to_numpy(), closes.loc[pen["ts"].str[:10]].to_numpy(),
                               rtol=0, atol=5e-7)
    # achieved weight of the sub-penny name: within one share (lot) under investment_cap * target
    targets = pd.DataFrame(st["weights_history"]).set_index("date")
    achieved = pd.DataFrame(st["achieved_weights_history"]).set_index("date")
    assert list(achieved.index) == list(targets.index) and list(achieved.columns) == MIXED_SYMS
    equity = res["equity"].copy()
    equity.index = equity.index.strftime("%Y-%m-%d")
    for sym, tick in (("PENNY", 1e-6), ("BIG", 0.01)):
        px = mixed_prices[sym].copy()
        px.index = px.index.strftime("%Y-%m-%d")
        lot = (px.loc[targets.index] + tick) / equity.loc[targets.index]  # one share, in weight
        gap = 0.98 * targets[sym] - achieved[sym]
        assert (gap >= -1e-6).all() and (gap <= lot + 1e-6).all(), (sym, gap.max(), lot.min())
    wt = st["weight_tracking"]
    assert wt["n_rebalances"] == st["n_rebalances"] and wt["investment_cap"] == 0.98
    assert wt["per_symbol"]["PENNY"]["max_abs_gap"] < 1e-6
    assert 0.95 < wt["mean_invested_fraction"] <= 0.98 + 1e-9
    if allocator == "fixed":
        assert st["fixed_weights_normalised"] == pytest.approx(MIXED_FIXED)
        # BIG (~400) with a 0.5% weight: ~980 of 200k buys 2 shares, visibly under target, and reported
        big = wt["per_symbol"]["BIG"]
        assert big["mean_abs_gap"] > 2e-4 and wt["max_abs_gap_symbol"] == "BIG"
        assert big["mean_achieved"] < big["mean_capped_target"]


def test_weight_tracking_summary():
    targets = [{"date": "d1", "A": 0.5, "B": 0.5}, {"date": "d2", "A": 0.5, "B": 0.5}]
    achieved = [{"date": "d1", "A": 0.49, "B": 0.40}, {"date": "d2", "A": 0.47, "B": 0.49}]
    wt = weight_tracking(targets, achieved, 0.98)
    assert wt["n_rebalances"] == 2
    assert wt["max_abs_gap"] == pytest.approx(0.09) and (wt["max_abs_gap_symbol"], wt["max_abs_gap_date"]) == ("B", "d1")
    assert wt["mean_abs_gap"] == pytest.approx((0.0 + 0.09 + 0.02 + 0.0) / 4)
    assert wt["per_symbol"]["A"] == pytest.approx({"mean_capped_target": 0.49, "mean_achieved": 0.48,
                                                   "mean_abs_gap": 0.01, "max_abs_gap": 0.02})
    assert wt["mean_invested_fraction"] == pytest.approx((0.89 + 0.96) / 2)
    empty = weight_tracking([], [], 0.98)
    assert empty["n_rebalances"] == 0 and empty["per_symbol"] == {} and math.isnan(empty["max_abs_gap"])


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
    # the canonical numbers in results/execution_summary.json (pinned versions, deterministic)
    assert st["n_fills"] == 573 and st["first_fill_date"] == "2016-12-30"
    assert hrp["final_equity"] == pytest.approx(2_479_775.76, abs=0.005)
    assert ew["final_equity"] == pytest.approx(2_838_765.94, abs=0.005)
    assert res["equal_pandas"]["metrics"]["final_equity"] == pytest.approx(2_804_157.82, abs=0.005)
    assert res["snapshot"].cash == pytest.approx(51_934.97, abs=0.005)
    assert st["n_equity_checks"] == len(res["prices"])
