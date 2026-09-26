"""Tests for quantstack.risk.bridge_test (ORE curve -> standalone QuantLib reprice).

The fast tests need nothing but QuantLib: a synthetic 3-pillar curves report
is rebuilt, the swap is priced, and QuantLib's plumbing is checked against an
exact identity (single-curve par-coupon float leg = N x (DF(start) - DF(end))).
They also cover input validation and the 'auto' companion discovery.  The
integration tests use the risk module's committed outputs (results/risk_*.csv,
risk_curve_pillars.csv) and are skipped when those have not been produced yet.
Everything runs in a few seconds; no ORE run is triggered here.
"""

from __future__ import annotations

import json
import math
import shutil
from datetime import date
from pathlib import Path

import numpy as np
import pytest

ql = pytest.importorskip("QuantLib")

from quantstack.risk import bridge_test as bt  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CURVES = REPO / "results" / "risk_curves.csv"
NPV = REPO / "results" / "risk_npv.csv"
CASHFLOWS = REPO / "results" / "risk_cashflows.csv"
PILLARS = REPO / "results" / "risk_curve_pillars.csv"
COMMITTED_SUMMARY = REPO / "results" / "bridge_summary.json"
NOTIONAL = 10_000_000.0

needs_ore_results = pytest.mark.skipif(
    not (CURVES.exists() and NPV.exists()),
    reason="results/risk_curves.csv / risk_npv.csv not present (run python -m quantstack.risk.run_ore)",
)


def _flat_df(d: date, rate: float = 0.01) -> float:
    return math.exp(-rate * (d - bt.ASOF).days / 365.0)


@pytest.fixture()
def synthetic_report(tmp_path: Path) -> Path:
    """An ORE-shaped curves report with only three pillars on a flat 1% curve."""
    dates = [date(2021, 2, 5), date(2026, 2, 5), date(2041, 2, 5)]
    lines = ["#Tenor,Date,EUR,EUR-EURIBOR-6M"]
    for tenor, d in zip(("60M", "120M", "300M"), dates):
        df = _flat_df(d)
        lines.append(f"{tenor},{d.isoformat()},{df!r},{df!r}")
    p = tmp_path / "curves.csv"
    p.write_text("\n".join(lines) + "\n")
    return p


# --------------------------------------------------------------------------
# fast, QuantLib only
# --------------------------------------------------------------------------


def test_synthetic_three_pillar_rebuild_and_price(synthetic_report: Path):
    rep = bt.read_curves_report(synthetic_report)
    assert list(rep.columns[:3]) == ["Tenor", "Date", "EUR"]  # '#' stripped
    curve = bt.build_curve(rep["date"], rep["EUR"], bt.ASOF)
    # (asof, 1.0) was prepended; the pillars are reproduced exactly
    assert curve.referenceDate() == ql.Date(5, 2, 2016)
    assert curve.discount(ql.Date(5, 2, 2016)) == pytest.approx(1.0, abs=1e-15)
    for d, df in zip(rep["date"], rep["EUR"]):
        assert curve.discount(bt._ql_date(d)) == pytest.approx(df, abs=1e-14)

    p = bt.price(curve)
    assert np.isfinite(p["npv"]) and np.isfinite(p["fair_rate"])
    assert p["historical_fixing_needed"] is False
    assert p["first_fixing_date"] == "2016-02-26"
    # Flat 1% curve: receiving 2% fixed is worth roughly (2% - ~1%) x annuity ~ +1.6M... positive.
    assert p["npv"] > 0
    # Single-curve, par coupons: the float leg telescopes exactly to N x (DF(start) - DF(end)).
    df_start = curve.discount(ql.Date(1, 3, 2016))
    df_end = curve.discount(ql.Date(3, 3, 2036))
    assert p["float_leg_npv"] == pytest.approx(-NOTIONAL * (df_start - df_end), abs=1e-6)


@pytest.mark.parametrize("method", ["loglinear_default", "loglinear_explicit", "monotonic_logcubic",
                                    "natural_logcubic", "linear_zero"])
def test_every_interpolation_variant_hits_the_nodes(synthetic_report: Path, method: str):
    rep = bt.read_curves_report(synthetic_report)
    curve = bt.build_curve(rep["date"], rep["EUR"], bt.ASOF, method=method)
    for d, df in zip(rep["date"], rep["EUR"]):
        assert curve.discount(bt._ql_date(d)) == pytest.approx(df, abs=1e-12)
    assert np.isfinite(bt.price(curve)["npv"])


def test_default_discount_curve_is_loglinear(synthetic_report: Path):
    rep = bt.read_curves_report(synthetic_report)
    a = bt.build_curve(rep["date"], rep["EUR"], method="loglinear_default")
    b = bt.build_curve(rep["date"], rep["EUR"], method="loglinear_explicit")
    for y in (2017, 2023, 2033, 2036):
        assert a.discount(ql.Date(15, 6, y)) == b.discount(ql.Date(15, 6, y))


def test_build_curve_rejects_nodes_before_asof():
    with pytest.raises(ValueError):
        bt.build_curve([date(2016, 1, 1), date(2020, 1, 1)], [1.0, 0.99], bt.ASOF)


def test_evaluation_date_is_restored(synthetic_report: Path):
    s = ql.Settings.instance()
    saved = s.evaluationDate
    s.evaluationDate = ql.Date(1, 1, 2020)
    try:
        rep = bt.read_curves_report(synthetic_report)
        bt.price(bt.build_curve(rep["date"], rep["EUR"]))
        assert s.evaluationDate == ql.Date(1, 1, 2020)
    finally:
        s.evaluationDate = saved  # whatever the process had, not todaysDate()


@pytest.mark.parametrize("dates, dfs, match", [
    ([], [], "no curve nodes"),
    ([date(2020, 1, 1)], [0.99, 0.98], "1 curve dates but 2"),
    ([date(2020, 1, 1), date(2021, 1, 1)], [0.99, float("nan")], "finite"),
    ([date(2020, 1, 1), date(2021, 1, 1)], [0.99, 0.0], "finite and > 0"),
    ([date(2020, 1, 1), date(2021, 1, 1)], [0.99, "x"], "not a number"),
    ([date(2020, 1, 1), None], [0.99, 0.98], "missing curve node date"),
    ([date(2020, 1, 1), float("nan")], [0.99, 0.98], "missing curve node date"),
    ([date(2020, 1, 1), np.datetime64("NaT", "D")], [0.99, 0.98], "missing curve node date"),
    ([date(2020, 1, 1), date(2020, 1, 1)], [0.99, 0.99], "given twice"),
])
def test_build_curve_rejects_bad_nodes(dates, dfs, match):
    with pytest.raises(ValueError, match=match):
        bt.build_curve(dates, dfs, bt.ASOF)


@pytest.mark.parametrize("body, match", [
    ("", "no rows"),
    ("60M,,0.95,0.95\n120M,2026-02-05,0.9,0.9\n", "unparseable date"),
    ("60M,not-a-date,0.95,0.95\n", "unparseable date"),
    ("60M,2021-02-05,0.95,0.95\n61M,2021-02-05,0.95,0.95\n", "duplicate date"),
])
def test_read_curves_report_rejects_bad_files(tmp_path: Path, body: str, match: str):
    p = tmp_path / "curves.csv"
    p.write_text("#Tenor,Date,EUR,EUR-EURIBOR-6M\n" + body)
    with pytest.raises(ValueError, match=match):
        bt.read_curves_report(p)


def test_schedule_follows_target_and_conventions(synthetic_report: Path):
    rep = bt.read_curves_report(synthetic_report)
    curve = bt.build_curve(rep["date"], rep["EUR"])
    with bt._evaluation_date(bt.ASOF):
        swap, _ = bt.build_swap(curve)
        rows = bt._ql_legs(swap, bt.SwapSpec())
    fixed = [d.isoformat() for d in rows.loc[rows["leg"] == "fixed", "pay_date"]]
    flt = rows[rows["leg"] == "float"]
    assert len(fixed) == 20 and len(flt) == 40
    # 2020-03-01 and 2025-03-01 are Sundays/Saturdays -> Following; 2036-03-01 is a Saturday
    assert {"2020-03-02", "2025-03-03", "2036-03-03"} <= set(fixed)
    assert flt["fixing_date"].iloc[0] == date(2016, 2, 26)  # 2 TARGET days before 2016-03-01
    assert rows.loc[rows["leg"] == "fixed", "accrual"].iloc[3] == pytest.approx(361 / 360)  # 30/360


def test_readers_accept_ore_and_summary_formats(tmp_path: Path):
    npv_csv = tmp_path / "npv.csv"
    npv_csv.write_text("#TradeId,TradeType,NPV,NPV(Base)\nOther,Swap,1.0,1.0\nSwap_20y,Swap,123.5,123.5\n")
    assert bt.read_ore_npv(npv_csv) == 123.5
    js = tmp_path / "risk_summary.json"
    js.write_text(json.dumps({"npv_base": 42.0}))
    assert bt.read_ore_npv(js) == 42.0

    cal = tmp_path / "todaysmarketcalibration.csv"
    cal.write_text(
        "#MarketObjectType,MarketObjectId,ResultId,ResultKey1,ResultKey2,ResultKey3,ResultType,ResultValue\n"
        "yieldCurve,EUR6M,dayCounter,,,,string,Actual/365 (Fixed)\n"
        "yieldCurve,EUR6M,time,2016-08-09,MM/RATE/EUR/2D/6M,,double,0.50958904\n"
        "yieldCurve,EUR6M,zeroRate,2016-08-09,MM/RATE/EUR/2D/6M,,double,0.00024940\n"
        "yieldCurve,EUR6M,discountFactor,2016-08-09,MM/RATE/EUR/2D/6M,,double,0.99987292\n"
        "yieldCurve,EUR1D,discountFactor,2016-08-09,X,,double,0.5\n"
    )
    nat = bt.read_native_pillars(cal, "EUR6M")
    assert list(nat["date"]) == [date(2016, 8, 9)]
    assert nat["discount"].iloc[0] == pytest.approx(0.99987292)
    assert nat.attrs["day_counter"] == "Actual/365 (Fixed)"
    assert nat.attrs["format"] == "todaysmarketcalibration"


def test_read_native_pillars_from_risk_curve_pillars_csv(tmp_path: Path):
    """The risk module's committed pillar file: same values, day counter identified from its zero rates."""
    rows = [(date(2016, 8, 9), 0.99987292), (date(2036, 2, 11), 0.795041)]

    def write(name, denom):
        lines = ["curve_id,date,discount_factor,zero_rate,forward_rate"]
        for d, df in rows:
            t = (d - bt.ASOF).days / denom
            lines.append(f"EUR6M,{d.isoformat()},{df},{round(-math.log(df) / t, 8)},0.01")
        lines.append("EUR1D,2016-08-09,0.5,0.1,0.1")
        p = tmp_path / name
        p.write_text("\n".join(lines) + "\n")
        return p

    nat = bt.read_native_pillars(write("risk_curve_pillars.csv", 365.0), "EUR6M")
    assert list(nat["date"]) == [d for d, _ in rows]
    assert list(nat["discount"]) == [df for _, df in rows]
    assert nat.attrs["format"] == "risk_curve_pillars"
    assert nat.attrs["day_counter"] == "Actual/365 (Fixed)" and nat.attrs["day_counter_fit"] < 1e-7
    # zero rates on another day counter are not passed off as A365F
    assert bt.read_native_pillars(write("a360.csv", 360.0), "EUR6M").attrs["day_counter"] is None
    with pytest.raises(KeyError):
        bt.read_native_pillars(tmp_path / "risk_curve_pillars.csv", "USD3M")


def test_companion_candidates_same_directory_and_prefix(tmp_path: Path):
    c = bt._companion_candidates(tmp_path / "risk_curves.csv")
    assert [p for p, _ in c["cashflows"]] == [tmp_path / "risk_cashflows.csv", tmp_path / "ore_output" / "flows.csv"]
    assert [p for p, _ in c["native_pillars"]] == [tmp_path / "risk_curve_pillars.csv",
                                                   tmp_path / "ore_output" / "todaysmarketcalibration.csv"]
    assert [p for p, _ in c["risk_summary"]] == [tmp_path / "risk_summary.json"]
    t = bt._companion_candidates(tmp_path / "risk_xois_eur_1000_curves.csv")
    assert [p for p, _ in t["cashflows"]] == [tmp_path / "risk_xois_eur_1000_cashflows.csv",
                                              tmp_path / "ore_output" / "xois_eur_1000" / "flows.csv"]
    assert t["risk_summary"][0][0] == tmp_path / "risk_xois_eur_1000_summary.json"
    o = bt._companion_candidates(tmp_path / "curves.csv")  # ORE's own output directory
    assert [p for p, _ in o["cashflows"]] == [tmp_path / "flows.csv"]
    assert [p for p, _ in o["native_pillars"]] == [tmp_path / "todaysmarketcalibration.csv"]
    assert o["risk_summary"] == []
    assert bt._companion_candidates(tmp_path / "my_grid.csv") == {
        "cashflows": [], "native_pillars": [], "risk_summary": []}


def test_auto_discovery_never_falls_back_to_repo_defaults(tmp_path: Path, synthetic_report: Path):
    """A curves file outside results/ must not pick up results/risk_cashflows.csv & co."""
    npv = tmp_path / "npv.csv"
    npv.write_text("#TradeId,NPV\nSwap_20y,1000.0\n")
    for curves in (synthetic_report, shutil.copy(synthetic_report, tmp_path / "my_grid.csv")):
        s = bt.compute_bridge(curves, npv).summary
        inp = s["inputs"]
        assert inp["cashflows"] is None and inp["native_pillars"] is None and inp["risk_summary"] is None
        assert all(v.startswith("auto:") for v in inp["found_by"].values())
        assert s["schedule_match"]["source"] is None and s["native_curve"] is None
        assert s["market_configuration"] is None and s["in_grid_residual"] is None


def test_past_fixing_is_loaded_from_ore_fixings_file(tmp_path: Path, synthetic_report: Path):
    """A trade whose first fixing is before the as-of needs index.addFixing (not hit by the article)."""
    fx = tmp_path / "fixings.txt"
    fx.write_text("20160128 EUR-EURIBOR-6M 0.0005\n#20160128 EUR-EURIBOR-6M 9.9\n")
    rep = bt.read_curves_report(synthetic_report)
    curve = bt.build_curve(rep["date"], rep["EUR"])
    spec = bt.SwapSpec(start=date(2016, 2, 1), end=date(2026, 2, 1))
    try:
        with bt._evaluation_date(bt.ASOF):
            swap, info = bt.build_swap(curve, spec=spec, fixings_file=fx)
            assert info["historical_fixing_needed"] is True
            assert info["historical_fixings"] == [{"date": "2016-01-28", "value": 0.0005}]
            first = ql.as_floating_rate_coupon(swap.floatingLeg()[0])
            assert first.rate() == pytest.approx(0.0005)
            assert np.isfinite(swap.NPV())
    finally:
        ql.IndexManager.instance().clearHistories()  # even if an assert failed


# --------------------------------------------------------------------------
# integration with the risk module's outputs (skipped if absent)
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def bridge_summary():
    if not (CURVES.exists() and NPV.exists()):
        pytest.skip("risk module outputs not present")
    return bt.run_bridge_test(CURVES, NPV)


@needs_ore_results
def test_bridge_reprices_within_5bp(bridge_summary):
    s = bridge_summary
    assert s["single_curve"] is True or s["market_configuration"] != "libor"
    assert abs(s["diff_bp"]) < 5.0
    assert s["diff_eur"] == pytest.approx(s["ore_npv"] - s["ql_npv"])
    assert s["historical_fixing_needed"] is False


@needs_ore_results
def test_bridge_reproduces_article_under_libor(bridge_summary):
    s = bridge_summary
    if s["market_configuration"] != "libor":
        pytest.skip("risk module was run under a different market configuration")
    assert s["ore_npv"] == pytest.approx(bt.ARTICLE["ore_npv"], abs=0.01)
    assert s["ql_npv"] == pytest.approx(bt.ARTICLE["ql_npv"], abs=0.01)
    assert s["diff_eur"] == pytest.approx(bt.ARTICLE["diff_eur"], abs=0.01)


@needs_ore_results
def test_schedules_match_ore_cashflow_report(bridge_summary):
    sm = bridge_summary["schedule_match"]
    if sm.get("source") is None:
        pytest.skip("no ORE cashflow report available")
    assert sm["all_match"], sm["mismatches"]
    assert sm["fixed_pay_dates_match"] and sm["float_pay_dates_match"] and sm["float_fixing_dates_match"]
    assert sm["n_fixed_ql"] == sm["n_fixed_ore"] == 20
    assert sm["n_float_ql"] == sm["n_float_ore"] == 40


@needs_ore_results
def test_residual_is_explained(bridge_summary):
    """Either the smoother variant is closer, or the residual is attributed - here both hold,
    and the attribution shows extrapolation past the grid end dominates."""
    s = bridge_summary
    v = {r["variant"]: r for r in s["variants"]}
    base = abs(v["grid_loglinear_default"]["diff_eur"])
    assert v["grid_loglinear_explicit"]["ql_npv"] == v["grid_loglinear_default"]["ql_npv"]
    assert s["smoother_interpolation_closer"] or "extrapolation_beyond_grid_end_eur" in s["gap_attribution"]
    if "grid_plus_ore_cashflow_df_tail" in v:
        # filling the 27 days beyond the grid with ORE's own DF closes > 99% of the gap
        assert abs(v["grid_plus_ore_cashflow_df_tail"]["diff_eur"]) < 0.01 * base
        a = s["gap_attribution"]
        assert a["extrapolation_beyond_grid_end_eur"] > 0.95 * s["diff_eur"]
    if "native_pillars_loglinear" in v:
        # ORE's own 14 LogLinear pillars reprice ORE to the calibration report's 8-dp rounding
        assert abs(v["native_pillars_loglinear"]["diff_eur"]) < 1.0
        assert s["max_abs_pv_diff_clean_cashflows_eur"] < 1e-6


@needs_ore_results
def test_in_grid_residual_is_the_fixed_leg(bridge_summary):
    """The ~5 EUR inside the grid: fixed coupons in native-pillar months; float pairs cancel."""
    ig = bridge_summary["in_grid_residual"]
    if ig is None:
        pytest.skip("needs ORE's cashflow report and native pillars")
    fx, pairs = ig["fixed_coupons_paid_in_pillar_months"], ig["float_coupon_pairs_across_pillar_months"]
    assert ig["attributed"] is True
    assert fx["sum_eur"] == pytest.approx(ig["total_eur"], abs=0.01)
    assert abs(pairs["sum_eur"]) < 1e-6 and abs(ig["float_leg_eur"]) < 1e-6
    assert pairs["max_abs_coupon_pv_diff_eur"] > 10.0  # individually large, they do cancel
    # the rebuild agrees with the per-cashflow view: inserting the pillars removes it
    assert ig["rebuild_check_eur"] == pytest.approx(-ig["total_eur"], abs=0.01)
    v = {r["variant"]: r for r in bridge_summary["variants"]}
    assert abs(v["grid_plus_native_pillars"]["diff_eur"]) < 1.0
    if bridge_summary["market_configuration"] == "libor":
        assert fx["n"] == 8 and pairs["n"] == 9
        assert fx["sum_eur"] == pytest.approx(-5.1758, abs=1e-3)


@needs_ore_results
def test_companions_from_another_run_are_rejected(tmp_path: Path):
    """'auto' only takes same-prefix files, and rejects them if they do not match the core inputs."""
    if not CASHFLOWS.exists():
        pytest.skip("results/risk_cashflows.csv not present")
    curves = shutil.copy(CURVES, tmp_path / "risk_x_curves.csv")
    shutil.copy(CASHFLOWS, tmp_path / "risk_x_cashflows.csv")
    ore_npv = bt.read_ore_npv(NPV)
    good, bad = tmp_path / "npv_good.csv", tmp_path / "npv_bad.csv"
    good.write_text(f"#TradeId,NPV\nSwap_20y,{ore_npv!r}\n")
    bad.write_text(f"#TradeId,NPV\nSwap_20y,{ore_npv + 1000.0!r}\n")
    s = bt.compute_bridge(curves, good).summary
    assert s["inputs"]["cashflows"].endswith("risk_x_cashflows.csv")
    assert s["inputs"]["native_pillars"] is None  # results/risk_curve_pillars.csv is NOT a companion
    with pytest.raises(ValueError, match="different run"):
        bt.compute_bridge(curves, bad)
    with pytest.warns(RuntimeWarning, match="PVs sum to"):
        bt.compute_bridge(curves, bad, cashflows_csv=tmp_path / "risk_x_cashflows.csv")
    if PILLARS.exists():
        text = PILLARS.read_text().replace("0.795041", "0.796041")  # the 20Y pillar of another curve
        (tmp_path / "risk_x_curve_pillars.csv").write_text(text)
        with pytest.raises(ValueError, match="log DF"):
            bt.compute_bridge(curves, good)


@needs_ore_results
def test_cli_without_optional_inputs(tmp_path: Path, capsys):
    """--cashflows none removes a stale table; no 'None' placeholders in the printout."""
    stale = tmp_path / "bridge_cashflows.csv"
    stale.write_text("stale\n")
    assert bt.main(["--curves", str(CURVES), "--npv", str(NPV), "--results", str(tmp_path),
                    "--cashflows", "none", "--no-figure"]) == 0
    assert not stale.exists()
    summary = json.loads((tmp_path / "bridge_summary.json").read_text())
    assert summary["inputs"]["cashflows"] is None and summary["inputs"]["found_by"]["cashflows"] == "disabled"
    assert "cashflows" not in summary["files"]
    assert bt.main(["--curves", str(CURVES), "--npv", str(NPV), "--results", str(tmp_path),
                    "--calibration", "none", "--no-figure"]) == 0
    out = capsys.readouterr().out
    assert "None" not in out  # no placeholder prints for the inputs that were switched off


@needs_ore_results
def test_committed_summary_regenerates_from_committed_inputs():
    """results/bridge_summary.json is reproducible from committed files only (no ore_output/)."""
    if not (COMMITTED_SUMMARY.exists() and CASHFLOWS.exists() and PILLARS.exists()):
        pytest.skip("committed bridge summary or its inputs not present")
    committed = json.loads(COMMITTED_SUMMARY.read_text())
    fresh = bt.run_bridge_test(CURVES, NPV, cashflows_csv=CASHFLOWS, calibration_csv=PILLARS)
    for key in ("curves", "npv", "cashflows", "native_pillars", "risk_summary"):
        assert "ore_output" not in str(committed["inputs"][key]), key

    def numbers(o, p=""):
        if isinstance(o, dict):
            for k, v in o.items():
                yield from numbers(v, f"{p}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                yield from numbers(v, f"{p}[{i}]")
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            yield p, o

    a, b = dict(numbers(committed)), dict(numbers(fresh))
    assert a.keys() == b.keys()
    for k, v in a.items():
        assert b[k] == pytest.approx(v, rel=1e-9, abs=1e-12), k


@needs_ore_results
def test_cli_writes_outputs(tmp_path: Path, capsys):
    assert bt.main(["--curves", str(CURVES), "--npv", str(NPV), "--results", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "QuantLib NPV" in out
    summary = json.loads((tmp_path / "bridge_summary.json").read_text())
    for key in ("ore_npv", "ql_npv", "diff_eur", "diff_bp", "variants", "schedule_match"):
        assert key in summary
    assert (tmp_path / "bridge_variants.csv").stat().st_size > 0
    assert (tmp_path / "figures" / "bridge_discount_curve.png").stat().st_size > 10_000
