"""Tests for quantstack.risk.bridge_test (ORE curve -> standalone QuantLib reprice).

The fast tests need nothing but QuantLib: a synthetic 3-pillar curves report
is rebuilt, the swap is priced, and QuantLib's plumbing is checked against an
exact identity (single-curve par-coupon float leg = N x (DF(start) - DF(end))).
The integration tests use the risk module's outputs (results/risk_*.csv) and
are skipped when those have not been produced yet.  Everything runs in a few
seconds; no ORE run is triggered here.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import numpy as np
import pytest

ql = pytest.importorskip("QuantLib")

from quantstack.risk import bridge_test as bt  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CURVES = REPO / "results" / "risk_curves.csv"
NPV = REPO / "results" / "risk_npv.csv"
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
    s.evaluationDate = ql.Date(1, 1, 2020)
    try:
        rep = bt.read_curves_report(synthetic_report)
        bt.price(bt.build_curve(rep["date"], rep["EUR"]))
        assert s.evaluationDate == ql.Date(1, 1, 2020)
    finally:
        s.evaluationDate = ql.Date.todaysDate()


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


def test_past_fixing_is_loaded_from_ore_fixings_file(tmp_path: Path, synthetic_report: Path):
    """A trade whose first fixing is before the as-of needs index.addFixing (not hit by the article)."""
    fx = tmp_path / "fixings.txt"
    fx.write_text("20160128 EUR-EURIBOR-6M 0.0005\n#20160128 EUR-EURIBOR-6M 9.9\n")
    rep = bt.read_curves_report(synthetic_report)
    curve = bt.build_curve(rep["date"], rep["EUR"])
    spec = bt.SwapSpec(start=date(2016, 2, 1), end=date(2026, 2, 1))
    with bt._evaluation_date(bt.ASOF):
        swap, info = bt.build_swap(curve, spec=spec, fixings_file=fx)
        assert info["historical_fixing_needed"] is True
        assert info["historical_fixings"] == [{"date": "2016-01-28", "value": 0.0005}]
        first = ql.as_floating_rate_coupon(swap.floatingLeg()[0])
        assert first.rate() == pytest.approx(0.0005)
        assert np.isfinite(swap.NPV())
    ql.IndexManager.instance().clearHistories()


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
def test_cli_writes_outputs(tmp_path: Path, capsys):
    assert bt.main(["--curves", str(CURVES), "--npv", str(NPV), "--results", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "QuantLib NPV" in out
    summary = json.loads((tmp_path / "bridge_summary.json").read_text())
    for key in ("ore_npv", "ql_npv", "diff_eur", "diff_bp", "variants", "schedule_match"):
        assert key in summary
    assert (tmp_path / "bridge_variants.csv").stat().st_size > 0
    assert (tmp_path / "figures" / "bridge_discount_curve.png").stat().st_size > 10_000
