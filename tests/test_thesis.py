"""Tests for quantstack.thesis: the user's thesis book through the execution engine.

Fast: synthetic panels for the data policy (late listings, gaps and the
3-bar forward-fill limit, the strict calendar, rescaling, repairs, the
manifest check), the holdings loader, both renormalisations, presets and the
CLI, a 5-holding synthetic end-to-end ``run_thesis`` (dashboard off, lookback
30, rebalance 10), and, when the thesis files are in the repo, the presets'
selections on the real ``prices_gbp_daily.csv`` plus ``--quick`` (about 5 s).
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from quantstack.contracts import equity_csv_columns, read_equity_csv
from quantstack.thesis import run as run_mod
from quantstack.thesis.data import (
    availability,
    engine_price_diagnostics,
    filled_cells,
    load_panel,
    rescale_for_engine,
    select_window,
    sha256_of,
    verify_panel_file,
)
from quantstack.thesis.repairs import REPAIRS, Repair, apply_repairs
from quantstack.thesis.report import _money_ticks, in_sample_stats, sharpe_rf, top_weights
from quantstack.thesis.run import (
    ALL_SCHEMES,
    DEFAULT_HOLDINGS,
    DEFAULT_PRICES,
    PRESETS,
    QUICK_BARS,
    QUICK_TICKERS,
    SCHEMES,
    THESIS_RF,
    allocation_stage,
    build_parser,
    fixed_weights_for,
    parse_schemes,
    quick_start,
    replay_dashboard,
    resolve,
    run_thesis,
    tracking_summary,
    whole_unit_check,
)
from quantstack.thesis.universe import (
    load_holdings,
    renormalise,
    renormalise_within_sleeves,
    sleeve_of,
    sleeve_split,
    thesis_weights,
)

REAL_DATA = DEFAULT_PRICES.is_file() and DEFAULT_HOLDINGS.is_file()
real_data = pytest.mark.skipif(not REAL_DATA, reason="thesis data files not in the repo")

# ----------------------------------------------------------------------------- synthetic data


def _walk(n: int, seed: int, start: float = 100.0, vol: float = 0.01) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return start * np.exp(np.cumsum(rng.normal(0.0003, vol, n)))


@pytest.fixture(scope="module")
def panel() -> pd.DataFrame:
    """60 business days: three clean names plus one of each data problem the policy handles."""
    idx = pd.bdate_range("2020-01-01", periods=60, name="date")
    df = pd.DataFrame({c: _walk(60, i) for i, c in enumerate(
        ["FULL1", "FULL2", "FULL3", "LEAD", "GAP2", "GAP9", "STALE", "TAIL2", "HOL"])}, index=idx)
    df.loc[idx[:10], "LEAD"] = np.nan          # lists on bar 10
    df.loc[idx[20:22], "GAP2"] = np.nan        # 2-bar interior gap
    df.loc[idx[30:39], "GAP9"] = np.nan        # 9-bar interior gap
    df.loc[idx[-8:], "STALE"] = np.nan         # stops 8 bars early
    df.loc[idx[-2:], "TAIL2"] = np.nan         # stops 2 bars early
    df.loc[idx[5], "HOL"] = np.nan             # one "holiday"
    df.loc[idx[40], "FULL3"] = df.loc[idx[39], "FULL3"] * 1.5  # a +50% spike...
    df.loc[idx[41]:, "FULL3"] = df.loc[idx[41]:, "FULL3"] * 1.5  # ...that persists
    return df


def _holdings_csv(path, rows):
    pd.DataFrame(rows, columns=["ticker", "name", "sleeve", "weight_total"]).to_csv(path, index=False)
    return path


# ----------------------------------------------------------------------------- load_panel, manifest


def test_load_panel_parses_the_unnamed_date_index_and_sorts(tmp_path):
    p = tmp_path / "p.csv"
    p.write_text(",A.L,BRK-B\n2020-01-03,2.0,4\n2020-01-02,1.0,\n2020-01-06,3.0,5.5\n")
    df = load_panel(p)
    assert list(df.columns) == ["A.L", "BRK-B"]
    assert df.index.name == "date" and df.index.is_monotonic_increasing
    assert list(df.index.strftime("%Y-%m-%d")) == ["2020-01-02", "2020-01-03", "2020-01-06"]
    assert df.dtypes.eq(float).all() and math.isnan(df.loc["2020-01-02", "BRK-B"])


@pytest.mark.parametrize(
    "text, match",
    [(",A,A\n2020-01-02,1,2\n", "duplicate column"),
     (",A\n2020-01-02,1\n2020-01-02,2\n", "duplicate date"),
     (",A\n02/01/2020,1\n", "ISO dates"),
     (",A\n2020-01-02 10:30,1\n", "time of day"),
     (",A\n2020-01-02,abc\n", "non-numeric"),
     (",A\n", "no rows"),
     ("date\n2020-01-02\n", "at least one price column")],
)
def test_load_panel_rejects_bad_files(tmp_path, text, match):
    p = tmp_path / "p.csv"
    p.write_text(text)
    with pytest.raises(ValueError, match=match):
        load_panel(p)
    with pytest.raises(ValueError, match="not found"):
        load_panel(tmp_path / "missing.csv")


def test_verify_panel_file_checks_the_manifest_and_shape(tmp_path):
    p = tmp_path / "prices.csv"
    p.write_text(",A,B\n2020-01-02,1,2\n")
    df = load_panel(p)
    out = verify_panel_file(p, df)
    assert out["manifest_match"] is None and "no _price_panel_manifest.json" in out["warning"]
    manifest = tmp_path / "_price_panel_manifest.json"
    manifest.write_text(json.dumps({"prices.csv": {"repaired_sha256": sha256_of(p), "as_of": "2020-01-02"}}))
    out = verify_panel_file(p, df, expected_shape=(1, 2))
    assert out["manifest_match"] is True and out["as_of"] == "2020-01-02" and out["warning"] is None
    with pytest.raises(ValueError, match=r"expected shape \(2526, 84\)"):
        verify_panel_file(p, df, expected_shape=(2526, 84))
    manifest.write_text(json.dumps({"prices.csv": {"repaired_sha256": "0" * 64}}))
    with pytest.raises(ValueError, match="does not match"):
        verify_panel_file(p, df)
    manifest.write_text(json.dumps({"other.csv": {"repaired_sha256": "0" * 64}}))
    assert "no checksum for prices.csv" in verify_panel_file(p, df)["warning"]


# ----------------------------------------------------------------------------- availability


def test_availability_reports_coverage_gaps_and_spikes(panel):
    a = availability(panel, ["FULL1", "LEAD", "GAP2", "GAP9", "STALE", "FULL3", "NOPE"])
    idx = panel.index
    assert list(a.index) == ["FULL1", "LEAD", "GAP2", "GAP9", "STALE", "FULL3", "NOPE"]
    assert a.loc["FULL1", "n_valid"] == 60 and a.loc["FULL1", "interior_nans"] == 0
    assert a.loc["LEAD", "first_valid"] == idx[10] and a.loc["LEAD", "n_valid"] == 50
    assert a.loc["LEAD", "interior_nans"] == 0  # leading NaNs are not gaps
    assert (a.loc["GAP2", "interior_nans"], a.loc["GAP2", "longest_interior_gap"]) == (2, 2)
    assert (a.loc["GAP9", "interior_nans"], a.loc["GAP9", "longest_interior_gap"]) == (9, 9)
    assert a.loc["STALE", "last_valid"] == idx[-9] and a.loc["STALE", "interior_nans"] == 0
    assert a.loc["FULL3", "max_abs_daily_return"] == pytest.approx(0.5, abs=0.05)
    assert a.loc["FULL3", "max_abs_return_date"] == idx[40]
    assert not a.loc["NOPE", "in_panel"] and a.loc["NOPE", "n_valid"] == 0 and pd.isna(a.loc["NOPE", "first_valid"])


# ----------------------------------------------------------------------------- select_window

ALL = ["FULL1", "FULL2", "FULL3", "LEAD", "GAP2", "GAP9", "STALE", "TAIL2", "HOL", "NOPE"]


def test_select_window_raises_on_gaps_longer_than_the_ffill_limit(panel):
    idx = panel.index
    with pytest.raises(ValueError, match=r"max_ffill_gap=3 .*'GAP9': '9 missing bars.*'STALE': 'last level"):
        select_window(panel, ALL, idx[0], idx[-1], lookback_bars=10)


def test_select_window_excludes_late_listings_and_forward_fills_short_gaps(panel):
    idx = panel.index
    w = dict.fromkeys(ALL, 0.1)
    prices, exc = select_window(panel, ALL, idx[0], idx[-1], lookback_bars=10, weights=w, gap_policy="exclude")
    assert list(prices.columns) == ["FULL1", "FULL2", "FULL3", "GAP2", "TAIL2", "HOL"]
    assert len(prices) == 60 and not prices.isna().any().any()
    reasons = dict(zip(exc["ticker"], exc["reason"]))
    assert reasons == {"LEAD": "listed_after_start", "GAP9": "interior_gap",
                       "STALE": "stale_at_end", "NOPE": "not_in_panel"}
    assert list(exc.columns) == ["ticker", "reason", "detail", "first_valid", "last_valid", "weight_total"]
    assert exc.set_index("ticker").loc["LEAD", "first_valid"] == idx[10]
    assert (exc["weight_total"] == 0.1).all()
    # the 2-bar gap and the 2-bar tail carry the last observed level (forward only)
    assert prices.loc[idx[21], "GAP2"] == panel.loc[idx[19], "GAP2"]
    assert prices.loc[idx[-1], "TAIL2"] == panel.loc[idx[-3], "TAIL2"]
    assert filled_cells(panel, prices) == {"FULL1": 0, "FULL2": 0, "FULL3": 0, "GAP2": 2, "TAIL2": 2, "HOL": 1}


def test_select_window_ffill_limit_is_the_threshold(panel):
    idx = panel.index
    prices, exc = select_window(panel, ALL[:-1], idx[0], idx[-1], lookback_bars=10, max_ffill_gap=1,
                                gap_policy="exclude")
    reasons = dict(zip(exc["ticker"], exc["reason"]))
    assert reasons["GAP2"] == "interior_gap" and reasons["TAIL2"] == "stale_at_end"
    assert "HOL" in prices.columns  # a 1-bar gap is still filled
    prices9, exc9 = select_window(panel, ALL[:-1], idx[0], idx[-1], lookback_bars=10, max_ffill_gap=9)
    assert list(exc9["ticker"]) == ["LEAD"] and "GAP9" in prices9  # 9-bar gap and 8-bar tail within the limit
    with pytest.raises(ValueError, match="gap_policy"):
        select_window(panel, ALL, idx[0], idx[-1], lookback_bars=10, gap_policy="guess")


def test_select_window_start_after_listing_and_after_a_gap(panel):
    idx = panel.index
    prices, exc = select_window(panel, ["FULL1", "FULL2", "LEAD", "GAP9"], idx[40], idx[-1], lookback_bars=10)
    assert list(prices.columns) == ["FULL1", "FULL2", "LEAD", "GAP9"] and exc.empty  # the gap ended before
    # a gap straddling the window start still counts in full
    with pytest.raises(ValueError, match="GAP9"):
        select_window(panel, ["FULL1", "FULL2", "FULL3", "GAP9"], idx[35], idx[-1], lookback_bars=10)


def test_select_window_carries_a_first_bar_holiday_in_from_before_the_window(panel):
    idx = panel.index
    prices, exc = select_window(panel, ["FULL1", "FULL2", "HOL"], idx[5], idx[-1], lookback_bars=10)
    assert exc.empty and prices.index[0] == idx[5]
    assert prices.loc[idx[5], "HOL"] == panel.loc[idx[4], "HOL"]
    assert not prices.iloc[0].isna().any()


def test_strict_calendar_drops_rows_instead_of_filling(panel):
    idx = panel.index
    prices, exc = select_window(panel, ["FULL1", "GAP2", "TAIL2", "HOL"], idx[0], idx[-1],
                                lookback_bars=10, strict_calendar=True)
    assert exc.empty and len(prices) == 60 - 2 - 2 - 1
    assert filled_cells(panel, prices) == dict.fromkeys(["FULL1", "GAP2", "TAIL2", "HOL"], 0)
    pd.testing.assert_frame_equal(prices, panel.loc[prices.index, list(prices.columns)])


@pytest.mark.parametrize(
    "kwargs, match",
    [({"tickers": ["FULL1", "LEAD", "NOPE"]}, "only 1 of 3 tickers"),
     ({"lookback_bars": 60}, "lookback_bars=60"),
     ({"start": "2020-06-01", "end": "2020-01-01"}, "is after end"),
     ({"start": "2021-01-01", "end": "2021-06-01"}, "no rows in"),
     ({"tickers": ["FULL1", "FULL1", "FULL2"]}, "duplicate tickers"),
     ({"max_ffill_gap": -1}, "max_ffill_gap"),
     ({"tickers": ["FULL1", "FULL2", "NEG"]}, "non-positive")],
)
def test_select_window_raises(panel, kwargs, match):
    p = panel.assign(NEG=panel["FULL1"].where(panel.index != panel.index[30], -1.0))
    args = {"tickers": ["FULL1", "FULL2", "FULL3"], "start": p.index[0], "end": p.index[-1],
            "lookback_bars": 10, **kwargs}
    with pytest.raises(ValueError, match=match):
        select_window(p, **args)


# ----------------------------------------------------------------------------- rescaling


def test_rescale_puts_every_minimum_at_100_and_keeps_returns(panel):
    raw = panel[["FULL1", "FULL2"]] * [0.0008, 26_000.0]  # LTBR-like and BRK-B-like levels
    rescaled, factors, check = rescale_for_engine(raw)
    assert rescaled.min().tolist() == pytest.approx([100.0, 100.0])
    assert factors.to_dict() == pytest.approx({"FULL1": 100 / raw["FULL1"].min(), "FULL2": 100 / raw["FULL2"].min()})
    assert check["max_abs_return_diff_unrounded"] < 1e-12
    assert check["max_abs_return_diff_after_rounding"] < 1e-7
    np.testing.assert_allclose(rescaled.pct_change().iloc[1:], raw.pct_change().iloc[1:], atol=1e-7)
    assert (rescaled.round(6) == rescaled).all().all()
    d = engine_price_diagnostics(rescaled)
    assert list(d.columns) == ["range_ratio", "engine_min", "engine_max"]
    assert d["range_ratio"].tolist() == pytest.approx((raw.max() / raw.min()).tolist())


def test_rescale_refuses_bad_input(panel):
    with pytest.raises(ValueError, match="floor must be > 0"):
        rescale_for_engine(panel[["FULL1"]], floor=0)
    with pytest.raises(ValueError, match="non-positive levels"):
        rescale_for_engine(panel[["FULL1"]].assign(Z=0.0))


# ----------------------------------------------------------------------------- repairs


def test_repair_undoes_an_unadjusted_consolidation(panel):
    idx = panel.index
    true = panel[["FULL1", "FULL2"]].copy()
    broken = true.copy()
    broken.loc[idx[:30], "FULL1"] *= 12  # levels before a 1:12 consolidation, left unadjusted
    assert broken["FULL1"].pct_change().iloc[30] == pytest.approx(true["FULL1"].pct_change().iloc[30] - 11 / 12,
                                                                  abs=0.1)
    fix = Repair("FULL1", idx[30].date().isoformat(), 12.0, "fake 1:12", "plausible")
    repaired, log = apply_repairs(broken, [fix])
    pd.testing.assert_frame_equal(repaired, true)
    assert log[0]["applied"] and log[0]["factor"] == 12.0 and log[0]["levels_divided"] == 30
    assert log[0]["return_before"] == pytest.approx(broken["FULL1"].iloc[30] / broken["FULL1"].iloc[29] - 1)
    assert log[0]["return_after"] == pytest.approx(true["FULL1"].pct_change().iloc[30])
    assert (broken["FULL2"] == repaired["FULL2"]).all()  # other columns untouched


def test_repair_without_a_divisor_neutralises_the_break_and_skips_absent_tickers(panel):
    idx = panel.index
    fix = Repair("FULL1", idx[30].date().isoformat(), None, "unknown ratio", "unverified")
    other = Repair("NOT_HERE", idx[30].date().isoformat(), 2.0, "absent", "unverified")
    repaired, log = apply_repairs(panel[["FULL1"]], [other, fix])
    assert repaired["FULL1"].pct_change().iloc[30] == pytest.approx(0.0, abs=1e-15)
    assert repaired["FULL1"].iloc[30:].equals(panel["FULL1"].iloc[30:])
    assert log[0] == {**log[0], "applied": False, "note": "ticker not in the panel"}
    assert log[1]["factor"] == pytest.approx(panel["FULL1"].iloc[29] / panel["FULL1"].iloc[30])


def test_repair_list_is_validated(panel):
    with pytest.raises(ValueError, match="no level on that date"):
        apply_repairs(panel, [Repair("FULL1", "2019-06-01", 2.0, "x", "plausible")])
    with pytest.raises(ValueError, match="no level before"):
        apply_repairs(panel, [Repair("FULL1", "2020-01-01", 2.0, "x", "plausible")])
    with pytest.raises(ValueError, match="verified must be"):
        Repair("A", "2020-01-02", 2.0, "x", "maybe")
    with pytest.raises(ValueError, match="divisor must be > 0"):
        Repair("A", "2020-01-02", 0.0, "x", "plausible")
    assert [(r.ticker, r.date, r.verified) for r in REPAIRS] == [("MSCL.TO", "2026-02-02", "plausible"),
                                                                  ("MSCL.TO", "2021-08-19", "unverified")]


@real_data
def test_real_msclto_repairs_match_the_data_plan():
    full = load_panel(DEFAULT_PRICES)
    _, log = apply_repairs(full[["MSCL.TO"]])
    first, second = log
    assert first["return_before"] == pytest.approx(-0.914, abs=0.001)
    assert first["return_after"] == pytest.approx(0.0323, abs=0.0005)
    assert second["return_before"] == pytest.approx(-0.953, abs=0.001) and second["return_after"] == 0.0
    assert second["factor"] == pytest.approx(21.29, abs=0.01)


# ----------------------------------------------------------------------------- universe


def test_load_holdings_and_weights(tmp_path):
    path = _holdings_csv(tmp_path / "h.csv", [(" AAA ", "a", "core", 0.5), ("BBB", "b", "Core", 0.3),
                                              ("CCC", "c", "moonshot", 0.1), ("DDD", "d", "moonshot", 0.1)])
    h = load_holdings(path, expected_n=4)
    assert thesis_weights(h) == {"AAA": 0.5, "BBB": 0.3, "CCC": 0.1, "DDD": 0.1}
    assert sleeve_of(h) == {"AAA": "core", "BBB": "core", "CCC": "moonshot", "DDD": "moonshot"}
    with pytest.raises(ValueError, match="expected 54 holdings, found 4"):
        load_holdings(path)


@pytest.mark.parametrize(
    "rows, match",
    [([("A", "a", "core", 0.5), ("A", "a", "core", 0.5)], "duplicate ticker"),
     ([("A", "a", "core", 0.5), ("", "b", "core", 0.5)], "empty ticker"),
     ([("A", "a", "core", 0.5), ("B", "b", "satellite", 0.5)], "sleeve must be one of"),
     ([("A", "a", "core", 0.5), ("B", "b", "core", -0.1)], "finite number >= 0"),
     ([("A", "a", "core", 0.5), ("B", "b", "core", None)], "finite number >= 0"),
     ([("A", "a", "core", 0.0), ("B", "b", "core", 0.0)], "positive total")],
)
def test_load_holdings_rejects_bad_rows(tmp_path, rows, match):
    with pytest.raises(ValueError, match=match):
        load_holdings(_holdings_csv(tmp_path / "h.csv", rows), expected_n=None)


def test_load_holdings_needs_its_columns(tmp_path):
    (tmp_path / "h.csv").write_text("ticker,sleeve\nA,core\n")
    with pytest.raises(ValueError, match=r"missing column\(s\) \['name', 'weight_total'\]"):
        load_holdings(tmp_path / "h.csv", expected_n=None)


W = {"C1": 0.5, "C2": 0.3, "M1": 0.1, "M2": 0.1}
SL = {"C1": "core", "C2": "core", "M1": "moonshot", "M2": "moonshot"}


def test_renormalise_spreads_excluded_weight_pro_rata():
    assert sleeve_split(W, SL) == pytest.approx({"core": 0.8, "moonshot": 0.2})
    r = renormalise(W, ["C1", "C2", "M1"])  # M2 excluded: its 10% is spread pro rata
    assert r == pytest.approx({"C1": 0.5 / 0.9, "C2": 0.3 / 0.9, "M1": 0.1 / 0.9})
    assert r["C1"] / r["C2"] == pytest.approx(0.5 / 0.3)
    assert sleeve_split(r, SL) == pytest.approx({"core": 0.8 / 0.9, "moonshot": 0.1 / 0.9})
    with pytest.raises(ValueError, match="no thesis weight"):
        renormalise(W, ["C1", "X"])
    with pytest.raises(ValueError, match="nothing to hold"):
        renormalise({"A": 0.0, "B": 0.0}, ["A", "B"])


def test_renormalise_within_sleeves_keeps_the_80_20_split():
    r = renormalise_within_sleeves(W, ["C1", "C2", "M1"], SL, {"core": 0.8, "moonshot": 0.2})
    assert r == pytest.approx({"C1": 0.5, "C2": 0.3, "M1": 0.2})  # M1 carries the whole moonshot sleeve
    assert sleeve_split(r, SL) == pytest.approx({"core": 0.8, "moonshot": 0.2})
    assert renormalise_within_sleeves(W, list(W), SL, {"core": 8, "moonshot": 2}) == pytest.approx(W)
    with pytest.raises(ValueError, match=r"sleeve\(s\) \['moonshot'\] have no included name"):
        renormalise_within_sleeves(W, ["C1", "C2"], SL, {"core": 0.8, "moonshot": 0.2})


# ----------------------------------------------------------------------------- presets on the real panel


def test_presets_are_well_formed():
    assert set(PRESETS) == {"thesis5y", "broad1y", "all54"}
    for p in PRESETS.values():
        assert parse_schemes(p.schemes) == p.schemes and p.start < p.end and p.lookback_bars >= 3
    assert PRESETS["thesis5y"].schemes == ALL_SCHEMES and "own_weights_8020" not in PRESETS["all54"].schemes
    assert (PRESETS["thesis5y"].start, PRESETS["thesis5y"].lookback_bars) == ("2020-12-10", 193)


@real_data
@pytest.mark.parametrize(
    "preset, n_names, first_trade, n_excluded, core_share",
    [("thesis5y", 35, "2021-09-16", 19, 0.876404),
     ("broad1y", 50, "2025-09-24", 4, 0.808290),
     ("all54", 54, "2026-07-10", 0, 0.8)],
)
def test_real_panel_preset_selections(preset, n_names, first_trade, n_excluded, core_share):
    h = load_holdings(DEFAULT_HOLDINGS)
    w, sl = thesis_weights(h), sleeve_of(h)
    full = load_panel(DEFAULT_PRICES)
    assert verify_panel_file(DEFAULT_PRICES, full, run_mod.CANONICAL_SHAPE)["manifest_match"] is True
    panel, _ = apply_repairs(full[list(h["ticker"])])
    p = PRESETS[preset]
    prices, exc = select_window(panel, list(h["ticker"]), p.start, p.end, p.lookback_bars, weights=w)
    assert prices.shape[1] == n_names and len(exc) == n_excluded
    assert set(exc["reason"]) <= {"listed_after_start"}
    assert prices.index[p.lookback_bars - 1].date().isoformat() == first_trade
    assert sleeve_split(renormalise(w, prices.columns), sl)["core"] == pytest.approx(core_share, abs=1e-6)
    rescaled, _, check = rescale_for_engine(prices)
    assert rescaled.min().min() == pytest.approx(100.0) and check["max_abs_return_diff_unrounded"] < 1e-12


# ----------------------------------------------------------------------------- run helpers


def test_parse_schemes():
    assert parse_schemes("own_weights, hrp_optimised") == ("own_weights", "hrp_optimised")
    assert parse_schemes(list(SCHEMES)) == tuple(SCHEMES)
    for spec, match in (("", "no schemes"), ("hrp", "unknown scheme"), ("hrp_optimised,hrp_optimised", "duplicate")):
        with pytest.raises(ValueError, match=match):
            parse_schemes(spec)


def test_fixed_weights_cover_exactly_the_panel_columns(panel):
    prices = panel[["FULL1", "FULL2"]]
    assert fixed_weights_for(prices, {"FULL2": 0.4, "FULL1": 0.6}) == {"FULL1": 0.6, "FULL2": 0.4}
    with pytest.raises(ValueError, match=r"no weight for \['FULL2'\]"):
        fixed_weights_for(prices, {"FULL1": 1.0})
    with pytest.raises(ValueError, match=r"weights without prices for \['X'\]"):
        fixed_weights_for(prices, {"FULL1": 0.5, "FULL2": 0.4, "X": 0.1})


def test_whole_unit_check_flags_targets_below_one_share():
    idx = pd.bdate_range("2020-01-01", periods=5)
    prices = pd.DataFrame({"CHEAP": 10.0, "DEAR": 5_000.0, "MID": 1_500.0}, index=idx)
    out = whole_unit_check(prices, lookback_bars=3, starting_cash=100_000, investment_cap=1.0,
                           targets={"own_weights": {"CHEAP": 0.9, "DEAR": 0.04, "MID": 0.06}})
    assert out["date"] == idx[2]
    own = out["schemes"]["own_weights"]
    assert [z["ticker"] for z in own["zero_units"]] == ["DEAR"]  # 4,000 of a 5,000 share
    assert own["zero_units"][0]["target_value"] == pytest.approx(4_000.0)
    assert own["under_3_units"] == []  # MID: 6,000 / 1,500 = 4 shares


def test_tracking_summary_condenses_the_engine_report():
    assert tracking_summary(None) is None and tracking_summary({"n_rebalances": 0}) is None
    wt = {"basis": "gap = ...", "n_rebalances": 3, "mean_abs_gap": 0.002, "max_abs_gap": 0.01,
          "max_abs_gap_symbol": "BRK-B", "max_abs_gap_date": "2021-10-15", "mean_invested_fraction": 0.985,
          "per_symbol": {"A": {"mean_capped_target": 0.5, "mean_achieved": 0.499, "mean_abs_gap": 0.001,
                               "max_abs_gap": 0.001},
                         "BRK-B": {"mean_capped_target": 0.01, "mean_achieved": 0.004, "mean_abs_gap": 0.006,
                                   "max_abs_gap": 0.01}}}
    t = tracking_summary(wt, "own_weights/execution_weights_fixed_achieved.csv", top=1)
    assert t["names_below_half_target"] == ["BRK-B"] and t["n_rebalances"] == 3
    assert t["largest_gaps"] == [{"ticker": "BRK-B", **wt["per_symbol"]["BRK-B"]}]
    assert t["achieved_csv"].endswith("_achieved.csv")


def test_in_sample_stats_use_the_allocation_module_formulas(panel):
    r = panel[["FULL1", "FULL2"]].pct_change().iloc[1:]
    st = in_sample_stats(r, {"FULL1": 0.25, "FULL2": 0.75})
    daily = 0.25 * r["FULL1"] + 0.75 * r["FULL2"]
    assert st["sharpe"] == pytest.approx(daily.mean() / daily.std(ddof=1) * math.sqrt(252))
    assert st["ann_vol"] == pytest.approx(daily.std(ddof=1) * math.sqrt(252))
    assert st["annualized_mean_arithmetic"] == pytest.approx(daily.mean() * 252)
    wealth = (1 + daily).cumprod()
    assert st["cagr"] == pytest.approx(wealth.iloc[-1] ** (252 / len(daily)) - 1)
    assert st["effective_n"] == pytest.approx(1 / (0.25**2 + 0.75**2))
    with pytest.raises(ValueError, match="fully invested"):
        in_sample_stats(r, {"FULL1": 0.25, "FULL2": 0.25})
    assert top_weights({"A": 0.2, "B": 0.5, "C": 0.2}, 2) == [("B", 0.5), ("A", 0.2)]
    assert sharpe_rf(0.2607, 0.1206, 0.0375) == pytest.approx(1.85, abs=0.01)
    assert math.isnan(sharpe_rf(0.1, 0.0, 0.0375)) and math.isnan(sharpe_rf(None, 0.1, 0.0375))


def test_allocation_stage_records_a_failing_optimiser(panel, monkeypatch):
    import quantstack.allocation.weights as w_mod

    r = panel[["FULL1", "FULL2", "FULL3"]].pct_change().iloc[1:]
    own = {"FULL1": 0.5, "FULL2": 0.3, "FULL3": 0.2}
    sleeves = {"FULL1": "core", "FULL2": "core", "FULL3": "moonshot"}
    targets = {"thesis_w_renormalised": own, "thesis_w_8020": None}
    table, summary = allocation_stage(r, own, targets, sleeves)
    assert list(table.columns) == ["ticker", "sleeve", "thesis_w", "thesis_w_renormalised", "thesis_w_8020",
                                   "equal_w", "hrp_w", "max_sharpe_w", "inv_var_w"]
    assert set(summary["stats"]) == {"thesis_w_renormalised", "equal_w", "hrp_w", "max_sharpe_w", "inv_var_w"}
    assert list(summary["errors"]) == ["thesis_w_8020"] and table["thesis_w_8020"].isna().all()
    for col in ("thesis_w_renormalised", "equal_w", "hrp_w", "max_sharpe_w", "inv_var_w"):
        assert table[col].sum() == pytest.approx(1.0, abs=1e-6)

    def boom():
        raise RuntimeError("solver failed")

    monkeypatch.setattr(w_mod, "build_max_sharpe", boom)
    table, summary = allocation_stage(r, own, targets, sleeves)
    assert summary["errors"]["max_sharpe_w"] == "RuntimeError: solver failed"
    assert table["max_sharpe_w"].isna().all() and "max_sharpe_w" not in summary["stats"]


def test_money_ticks_label_narrow_and_wide_ranges():
    assert _money_ticks(194_000, 250_000) == [200_000, 210_000, 220_000, 230_000, 240_000, 250_000]
    assert len(_money_ticks(150_000, 900_000)) >= 3 and len(_money_ticks(199_000, 201_000)) >= 3


# ----------------------------------------------------------------------------- end to end (synthetic)

SYMS = ["AAA.L", "BBB", "CCC.AX", "DDD", "LATE"]
E2E = dict(start="2020-01-01", end="2020-12-31", lookback_bars=30, rebalance_every=10, dashboard=False,
           expected_holdings=None)


@pytest.fixture(scope="module")
def thesis_inputs(tmp_path_factory):
    d = tmp_path_factory.mktemp("thesis_inputs")
    idx = pd.bdate_range("2020-01-01", periods=140)
    px = pd.DataFrame({s: _walk(140, 10 + i, vol=0.012) for i, s in enumerate(SYMS)}, index=idx)
    px["BBB"] *= 0.001  # a sub-penny level: the rescale lifts it to 100
    px.loc[idx[:31], "LATE"] = np.nan  # lists after the start: excluded, weight redistributed
    px.to_csv(d / "prices.csv", index_label="")  # the real file's layout: an empty first header cell
    _holdings_csv(d / "holdings.csv", [("AAA.L", "a", "core", 0.4), ("BBB", "b", "core", 0.25),
                                       ("CCC.AX", "c", "core", 0.15), ("DDD", "d", "moonshot", 0.1),
                                       ("LATE", "e", "moonshot", 0.1)])
    return d


@pytest.fixture(scope="module")
def e2e(thesis_inputs, tmp_path_factory):
    out = tmp_path_factory.mktemp("thesis_out")
    summary = run_thesis(thesis_inputs / "prices.csv", thesis_inputs / "holdings.csv", out, **E2E)
    return summary, out


def test_run_thesis_writes_a_result_folder_per_scheme(e2e):
    summary, out = e2e
    assert summary["status"] == "ok" and summary["config"]["schemes"] == list(ALL_SCHEMES)
    for scheme, alloc in SCHEMES.items():
        d = out / scheme
        for name in ("execution_equity.csv", "execution_fills.csv", "execution_positions.csv",
                     f"execution_weights_{alloc}.csv", f"execution_weights_{alloc}_achieved.csv",
                     "execution_summary.json", "figures/execution_equity.png"):
            assert (d / name).is_file(), f"{scheme}/{name}"
        ex = json.loads((d / "execution_summary.json").read_text())
        assert ex["scheme"] == scheme and ex[alloc]["metrics"]["final_equity"] == pytest.approx(
            summary["schemes"][scheme]["final_equity"])
        assert ex["fills"] == summary["schemes"][scheme]["fills"] > 0
        assert ex["universe"] == ["AAA.L", "BBB", "CCC.AX", "DDD"]
        assert "achieved_weights_history" not in ex[alloc]["stats"] and "weight_tracking" in ex[alloc]["stats"]
    for name in ("thesis_summary.json", "thesis_comparison.md", "thesis_equity.csv", "data_availability.csv",
                 "figures/thesis_equity.png", "figures/thesis_weights.png",
                 "allocation/thesis_allocation_weights.csv", "allocation/thesis_allocation_summary.json"):
        assert (out / name).is_file() and (out / name).stat().st_size > 0, name


def test_run_thesis_summary_keys_exclusions_and_splits(e2e):
    summary, out = e2e
    assert json.loads((out / "thesis_summary.json").read_text()) == summary
    assert {"config", "window", "universe", "exclusions", "repairs", "panel_check", "engine_prices",
            "whole_unit_check", "schemes", "benchmarks", "thesis_comparators", "allocation", "caveats",
            "outputs", "runtime_seconds"} <= set(summary)
    scale = summary["config"]["equity_scale"]
    assert scale == pytest.approx(200_000 / 100_000_000) and summary["config"]["investment_cap"] == 0.99
    for rec in summary["schemes"].values():
        assert {"cagr", "ann_vol", "sharpe", "sharpe_rf_thesis", "max_drawdown", "turnover_annual_oneway",
                "fills", "denied", "rejections", "first_fill_date", "final_equity", "final_equity_book"} <= set(rec)
        assert rec["denied"] == 0 and rec["rejections"] == 0 and rec["n_names_held_at_end"] == 4
        assert rec["final_equity_book"] == pytest.approx(rec["final_equity"] * scale)
        assert rec["sharpe_rf_thesis"] == pytest.approx((rec["cagr"] - THESIS_RF) / rec["ann_vol"])
        assert rec["target_vs_achieved"]["n_rebalances"] > 0
    u = summary["universe"]
    assert (u["n_universe"], u["n_included"], u["excluded"]) == (5, 4, ["LATE"])
    assert summary["exclusions"][0]["reason"] == "listed_after_start"
    assert summary["exclusions"][0]["sleeve"] == "moonshot" and summary["exclusions"][0]["weight_total"] == 0.1
    assert u["sleeve_split"]["thesis"] == pytest.approx({"core": 0.8, "moonshot": 0.2})
    assert u["sleeve_split"]["after"] == pytest.approx({"core": 0.8 / 0.9, "moonshot": 0.1 / 0.9})
    s = summary["schemes"]
    assert s["own_weights"]["intended_sleeve_split"] == pytest.approx({"core": 0.8 / 0.9, "moonshot": 0.1 / 0.9})
    assert s["own_weights_8020"]["intended_sleeve_split"] == pytest.approx({"core": 0.8, "moonshot": 0.2})
    assert s["equal_weight"]["intended_sleeve_split"] == pytest.approx({"core": 0.75, "moonshot": 0.25})
    assert summary["engine_prices"]["rescaled"] is True
    assert min(d["engine_min"] for d in summary["engine_prices"]["diagnostics"].values()) == pytest.approx(100.0)
    assert summary["panel_check"]["warning"] and summary["panel_check"]["manifest_match"] is None
    assert [r["applied"] for r in summary["repairs"]] == [False, False]  # MSCL.TO is not in this panel
    assert summary["checks"]["equal_engine_benchmark_consistent"] is True
    w = summary["window"]
    assert (w["first_bar"], w["trading_days"]) == ("2020-01-01", 140)
    assert w["first_fill_date"] == pd.bdate_range("2020-01-01", periods=140)[29].date().isoformat()


def test_fixed_weight_runs_trade_their_targets(e2e):
    summary, out = e2e
    own, own8020 = summary["universe"]["own_weights_renormalised"], summary["universe"]["own_weights_8020"]
    assert own == pytest.approx({"AAA.L": 0.4 / 0.9, "BBB": 0.25 / 0.9, "CCC.AX": 0.15 / 0.9, "DDD": 0.1 / 0.9})
    assert own8020 == pytest.approx({"AAA.L": 0.4, "BBB": 0.25, "CCC.AX": 0.15, "DDD": 0.2})
    for scheme, target in (("own_weights", own), ("own_weights_8020", own8020)):
        w = pd.read_csv(out / scheme / "execution_weights_fixed.csv")
        np.testing.assert_allclose(w[list(target)].to_numpy(), np.tile(list(target.values()), (len(w), 1)), atol=1e-6)
    alloc = pd.read_csv(out / "allocation" / "thesis_allocation_weights.csv").set_index("ticker")
    assert list(alloc.columns) == ["sleeve", "thesis_w", "thesis_w_renormalised", "thesis_w_8020", "equal_w",
                                   "hrp_w", "max_sharpe_w", "inv_var_w"]
    assert alloc["thesis_w"].to_dict() == {"AAA.L": 0.4, "BBB": 0.25, "CCC.AX": 0.15, "DDD": 0.1}
    assert alloc["thesis_w_8020"].to_dict() == pytest.approx(own8020)


def test_thesis_equity_csv_has_book_and_engine_curves_aligned_with_each_run(e2e):
    summary, out = e2e
    path = out / "thesis_equity.csv"
    assert equity_csv_columns(path) == ([f"equity_{s}" for s in ALL_SCHEMES]
                                        + [f"equity_{s}_engine" for s in ALL_SCHEMES])
    both = pd.read_csv(path, index_col="date")
    assert not both.isna().any().any() and both.index.is_monotonic_increasing
    scale = summary["config"]["equity_scale"]
    for scheme, alloc in SCHEMES.items():
        engine = read_equity_csv(out / scheme / "execution_equity.csv", f"equity_{alloc}")
        mine = read_equity_csv(path, f"equity_{scheme}_engine")
        pd.testing.assert_index_equal(mine.index, engine.index)
        np.testing.assert_allclose(mine.to_numpy(), engine.to_numpy(), atol=0.005)
        np.testing.assert_allclose(read_equity_csv(path, f"equity_{scheme}").to_numpy(),
                                   engine.to_numpy() * scale, atol=0.005)


def test_comparison_markdown_has_every_section(e2e):
    summary, out = e2e
    md = (out / "thesis_comparison.md").read_text()
    for heading in ("## Window", "## Data", "## Universe", "### Excluded", "## Results", "## Thesis comparators",
                    "## Largest weights", "## Target vs achieved weights", "## Allocation stage (in-sample)",
                    "## Caveats"):
        assert heading in md
    for label in ("Own (thesis) weights", "Own weights, 80/20 sleeves", "Equal weight", "HRP (pipeline optimiser)",
                  "Equal weight, pandas buy-and-hold", "Sharpe, rf = 3.75%", "Moderate12", "LATE", "Look-ahead",
                  "Intended sleeve split"):
        assert label in md, label
    assert f"{summary['schemes']['own_weights']['final_equity_book']:,.2f}" in md


def test_run_thesis_is_deterministic_and_rescaling_is_optional(e2e, thesis_inputs, tmp_path):
    summary, _ = e2e
    again = run_thesis(thesis_inputs / "prices.csv", thesis_inputs / "holdings.csv", tmp_path / "again",
                       schemes=("own_weights",), **E2E)
    assert again["schemes"]["own_weights"]["final_equity"] == summary["schemes"]["own_weights"]["final_equity"]
    assert again["schemes"]["own_weights"]["fills"] == summary["schemes"]["own_weights"]["fills"]
    raw = run_thesis(thesis_inputs / "prices.csv", thesis_inputs / "holdings.csv", tmp_path / "raw",
                     schemes=("equal_weight",), rescale=False, repairs=False, **E2E)
    ep = raw["engine_prices"]
    assert ep["rescaled"] is False and ep["factors"] is None and raw["repairs"] == []
    assert min(d["engine_min"] for d in ep["diagnostics"].values()) < 1  # BBB's sub-penny level, traded as is
    assert raw["schemes"]["equal_weight"]["status"] == "ok"
    assert any("--no-rescale" in c for c in raw["caveats"])


def test_a_failing_scheme_is_recorded_and_the_others_still_run(thesis_inputs, tmp_path, monkeypatch):
    real = run_mod.run_scheme

    def flaky(scheme, *a, **k):
        if scheme == "hrp_optimised":
            raise ValueError("engine exploded")
        return real(scheme, *a, **k)

    monkeypatch.setattr(run_mod, "run_scheme", flaky)
    s = run_thesis(thesis_inputs / "prices.csv", thesis_inputs / "holdings.csv", tmp_path,
                   schemes=("equal_weight", "hrp_optimised"), **E2E)
    assert s["status"] == "failed"
    assert s["schemes"]["hrp_optimised"] == {**s["schemes"]["hrp_optimised"], "status": "failed",
                                             "error": "ValueError: engine exploded"}
    assert s["schemes"]["equal_weight"]["status"] == "ok"
    assert equity_csv_columns(tmp_path / "thesis_equity.csv") == ["equity_equal_weight", "equity_equal_weight_engine"]
    assert "**hrp_optimised failed:** ValueError: engine exploded" in (tmp_path / "thesis_comparison.md").read_text()


def test_bad_inputs_raise_before_any_engine(thesis_inputs, tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "run_scheme", lambda *a, **k: pytest.fail("engine started"))
    p, h = thesis_inputs / "prices.csv", thesis_inputs / "holdings.csv"
    for kwargs, match in (({"schemes": ("minvar",)}, "unknown scheme"),
                          ({"lookback_bars": 200}, "lookback_bars=200"),
                          ({"investment_cap": 1.5}, "investment_cap"),
                          ({"tickers": ["AAA.L", "ZZZ"]}, "not in holdings.csv"),
                          ({"expected_holdings": 54}, "expected 54 holdings"),
                          ({"preset": "thesis10y"}, "unknown preset"),
                          ({"tickers": ["AAA.L", "BBB", "CCC.AX"]}, r"sleeve\(s\) \['moonshot'\]")):
        with pytest.raises(ValueError, match=match):
            run_thesis(p, h, tmp_path, **{**E2E, **kwargs})


def test_dashboard_replay_ok_and_failure_is_recorded_not_raised(e2e, tmp_path):
    _, out = e2e
    ok = replay_dashboard(out / "equal_weight")
    assert ok["status"] == "ok" and ok["error"] is None
    assert ok["table_sizes_after_load"]["equity"] == 140 and ok["equity_source_column"] == "equity_equal"
    assert (out / "equal_weight" / "dashboard_summary.json").is_file()
    empty = tmp_path / "empty_scheme"
    empty.mkdir()
    bad = replay_dashboard(empty)  # no CSVs: the server falls back to demo data
    assert bad["status"] == "failed" and bad["error"]


# ----------------------------------------------------------------------------- CLI


def test_cli_defaults_and_flags():
    a = build_parser().parse_args([])
    assert (a.preset, a.prices, a.holdings, a.results) == ("thesis5y", str(DEFAULT_PRICES), str(DEFAULT_HOLDINGS), None)
    assert (a.start, a.end, a.lookback, a.rebalance_every, a.schemes) == (None, None, None, None, None)
    assert (a.cash, a.investment_cap, a.max_ffill_gap) == (100_000_000, 0.99, 3)
    assert not (a.quick or a.no_dashboard or a.strict_calendar or a.no_rescale or a.no_repairs)
    a = build_parser().parse_args(["--preset", "all54", "--quick", "--no-dashboard", "--schemes", "hrp_optimised",
                                   "--lookback", "60", "--no-rescale", "--no-repairs", "--strict-calendar"])
    assert a.quick and a.no_dashboard and a.no_rescale and a.no_repairs and a.strict_calendar
    assert (a.preset, a.schemes, a.lookback) == ("all54", "hrp_optimised", 60)


def test_resolve_applies_the_preset_then_the_overrides(thesis_inputs):
    base = ["--prices", str(thesis_inputs / "prices.csv"), "--holdings", str(thesis_inputs / "holdings.csv")]
    kw = resolve(build_parser().parse_args(base + ["--preset", "broad1y"]))
    assert (kw["start"], kw["end"], kw["lookback_bars"], kw["rebalance_every"]) == ("2024-09-26", "2026-09-16", 252, 21)
    assert kw["schemes"] == ALL_SCHEMES and kw["preset"] == "broad1y" and kw["rescale"] and kw["repairs"]
    assert kw["results_dir"] == run_mod.RESULTS_ROOT / "broad1y" and kw["tickers"] is None
    kw = resolve(build_parser().parse_args(base + ["--start", "2020-01-01", "--lookback", "30", "--schemes",
                                                   "equal_weight", "--no-rescale", "--results", "x"]))
    assert (kw["start"], kw["end"], kw["lookback_bars"]) == ("2020-01-01", PRESETS["thesis5y"].end, 30)
    assert kw["schemes"] == ("equal_weight",) and not kw["rescale"] and str(kw["results_dir"]) == "x"


def test_cli_bad_scheme_exits_2(thesis_inputs, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        run_mod.main(["--prices", str(thesis_inputs / "prices.csv"), "--holdings", str(thesis_inputs / "holdings.csv"),
                      "--results", str(tmp_path), "--schemes", "hrp"])
    assert exc.value.code == 2 and "unknown scheme" in capsys.readouterr().err


def test_quick_start_counts_bars_back_from_end(panel):
    assert quick_start(panel, panel.index[-1], bars=10) == panel.index[-10].date().isoformat()
    with pytest.raises(ValueError, match="needs 100 bars"):
        quick_start(panel, panel.index[-1], bars=100)


@real_data
def test_cli_bad_window_exits_2_before_any_engine(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(run_mod, "run_scheme", lambda *a, **k: pytest.fail("engine started"))
    with pytest.raises(SystemExit) as exc:
        run_mod.main(["--start", "2026-09-01", "--end", "2026-01-01", "--results", str(tmp_path)])
    assert exc.value.code == 2 and "is after end" in capsys.readouterr().err
    with pytest.raises(SystemExit) as exc:  # 11 bars cannot warm up the preset's 193-bar lookback
        run_mod.main(["--start", "2026-09-01", "--results", str(tmp_path)])
    assert exc.value.code == 2 and "lookback_bars=193" in capsys.readouterr().err


@real_data
def test_cli_quick_on_the_real_panel(tmp_path):
    """``--quick``: six real names, the last 400 bars, every thesis5y scheme (about 5 s)."""
    code = run_mod.main(["--quick", "--no-dashboard", "--results", str(tmp_path)])
    s = json.loads((tmp_path / "thesis_summary.json").read_text())
    assert code == 0 and s["status"] == "ok" and s["panel_check"]["manifest_match"] is True
    assert s["universe"]["included"] == [t for t in load_holdings(DEFAULT_HOLDINGS)["ticker"] if t in QUICK_TICKERS]
    assert s["window"]["trading_days"] == QUICK_BARS and s["window"]["last_bar"] == "2026-09-16"
    assert s["preset"]["name"] == "thesis5y" and s["preset"]["matches_preset"] is False
    assert s["schemes"]["own_weights_8020"]["intended_sleeve_split"] == pytest.approx({"core": 0.8, "moonshot": 0.2})
    for rec in s["schemes"].values():
        assert rec["status"] == "ok" and rec["fills"] > 0 and rec["denied"] == 0 and not rec["halted_early"]
