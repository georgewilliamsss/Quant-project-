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
    write_results,
)
from quantstack.execution.data import (
    load_prices,
    make_bar_types,
    make_bars,
    make_close_trades,
    make_instruments,
    validate_symbols,
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
    assert set(paths) == {"equity_csv", "fills_csv", "positions_csv", "weights_csv"}
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
     ({"AAA": 1, "BBB": 1, "CCC": 1, "DDD": 1, "ZZZ": 4}, [0.25] * 4)],         # ZZZ not traded: dropped
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
     ("w.csv", {"w.csv": "ticker,w\nAAPL,1\n"}, "symbol,weight"),
     ("w.csv", {"w.csv": "symbol,weight\nAAPL,\n"}, "not a number")],
)
def test_parse_fixed_weights_rejects_bad_specs(tmp_path, monkeypatch, spec, files, match):
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    monkeypatch.chdir(tmp_path)  # relative file specs resolve here
    with pytest.raises(ValueError, match=match):
        parse_fixed_weights(spec)


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
    assert equity_csv_columns(out / "execution_equity.csv") == equity_columns("fixed")
    w = pd.read_csv(out / "execution_weights_fixed.csv")
    np.testing.assert_allclose(w[SYMS].to_numpy(), np.tile([0.5, 0.3, 0.2], (len(w), 1)), rtol=0, atol=1e-6)


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
