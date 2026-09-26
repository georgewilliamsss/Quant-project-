"""Tests for quantstack.risk (ORE exposure/XVA run + positions -> ORE portfolio wire).

Fast tests (~10 s together) check the input set, the report conversion, the
path resolution and market-configuration validation, the portfolio writer
against ORE's own parser (and its input validation), 16-path runs of the article
input, of a renamed-trade copy and of a two-trade / two-netting-set copy, the
native curve pillars export, the committed results files, and that ORE's
*silent* failure modes are turned into loud errors.  The full 1000 x 81
reproduction of the article is marked ``slow``.

ORE is imported only when a test runs (the ``ore`` fixture), never at collection
time.  ``import ORE`` and ``import QuantLib`` share one SWIG type table: the
module imported *last* supplies the Python proxy classes for the C++ types both
wrap, so importing ORE after another test module has imported QuantLib makes
later QuantLib calls (e.g. ``ql.as_floating_rate_coupon(c).fixingDate()`` in the
bridge tests) dispatch into ORE's binary and segfault.  Importing ORE first and
QuantLib afterwards is safe for both.
"""

from __future__ import annotations

import importlib.util
import json
import math
import shutil
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quantstack.contracts import Position, PositionSnapshot, write_positions_csv
from quantstack.risk import portfolio_writer as pw
from quantstack.risk import run_ore

pytestmark = pytest.mark.skipif(importlib.util.find_spec("ORE") is None,
                                reason="ORE (open-source-risk-engine wheel) not installed")

INPUT = run_ore.DEFAULT_INPUT_DIR
RESULTS = run_ore.DEFAULT_RESULTS_DIR
ARTICLE_NPV = 1_609_885.84
#: flat summary keys of a one-trade / one-netting-set run (the article case)
FLAT_KEYS = [
    "ore_version", "wall_time_s", "market_configuration", "trade_id", "netting_set", "cube",
    "npv_base", "npv_currency", "cva", "dva", "fba", "fca", "BaselEPE", "BaselEEPE", "fva",
    "cva_pct_notional", "exposure_rows", "exposure_future_dates", "horizon_years", "epe_t0",
    "max_epe", "max_epe_time_years", "max_epe_date", "max_ene", "max_ene_time_years", "max_pfe",
    "max_pfe_time_years",
]


def _params(elem):
    return {p.get("name"): (p.text or "").strip() for p in elem.findall("Parameter")}


def _analytics(root):
    return {a.get("type"): _params(a) for a in root.find("Analytics").findall("Analytic")}


@pytest.fixture(scope="module")
def ore():
    """The ORE module, imported lazily (see the module docstring)."""
    import ORE

    return ORE


@pytest.fixture()
def staged_input(tmp_path: Path) -> Path:
    """A private copy of the input set that a test may modify."""
    dst = tmp_path / "input"
    shutil.copytree(INPUT, dst)
    return dst


@pytest.fixture(scope="module")
def smoke16(tmp_path_factory) -> dict:
    """One 16-path run of the article input, shared by the tests that only read it."""
    return run_ore.run_exposure(INPUT, tmp_path_factory.mktemp("smoke16") / "out", samples=16)


# --------------------------------------------------------------------------
# input set
# --------------------------------------------------------------------------


def test_input_dir_is_self_contained():
    ore_xml = INPUT / "ore.xml"
    root = ET.parse(ore_xml).getroot()
    setup = _params(root.find("Setup"))
    assert setup["inputPath"] == "."
    assert not Path(setup["outputPath"]).is_absolute()
    assert setup["asofDate"] == "2016-02-05"

    referenced = run_ore.referenced_input_files(ore_xml)
    expected = {
        "market_20160205.txt", "fixings_20160205.txt", "curveconfig.xml", "conventions.xml",
        "todaysmarket.xml", "pricingengine.xml", "portfolio_swap.xml", "calendaradjustment.xml",
        "currencies.xml", "simulation.xml", "netting.xml",
    }
    assert expected <= set(referenced)
    for name in referenced:
        assert not Path(name).is_absolute() and ".." not in Path(name).parts, name
        assert (INPUT / name).is_file(), f"{name} referenced by ore.xml but missing from {INPUT}"
    # every referenced XML file is well-formed
    for name in referenced:
        if name.endswith(".xml"):
            ET.parse(INPUT / name)


def test_ore_xml_configuration_matches_the_article_case():
    root = ET.parse(INPUT / "ore.xml").getroot()
    markets = _params(root.find("Markets"))
    assert set(markets.values()) == {"libor"}
    a = _analytics(root)
    assert a["curves"]["active"] == "Y"
    assert a["curves"]["grid"] == "240,1M"
    assert a["curves"]["outputFileName"] == "curves.csv"
    assert a["curves"]["configuration"] == "libor"
    xva = a["xva"]
    assert xva["exposureProfiles"] == "Y" and xva["exposureProfilesByTrade"] == "Y"
    assert float(xva["quantile"]) == 0.95
    assert (xva["cva"], xva["dva"], xva["fva"]) == ("Y", "Y", "Y")
    assert a["simulation"]["active"] == "Y" and a["npv"]["active"] == "Y"

    sim = ET.parse(INPUT / "simulation.xml").getroot()
    assert sim.findtext("Parameters/Samples").strip() == "1000"
    assert sim.findtext("Parameters/Grid").strip() == "81,3M"

    pe = ET.parse(INPUT / "pricingengine.xml").getroot()
    swap = [p for p in pe.findall("Product") if p.get("type") == "Swap"][0]
    assert swap.findtext("Engine") == "DiscountingSwapEngine"

    trade = ET.parse(INPUT / "portfolio_swap.xml").getroot().find("Trade")
    assert trade.get("id") == "Swap_20y"
    legs = trade.findall("SwapData/LegData")
    fixed = [leg for leg in legs if leg.findtext("LegType") == "Fixed"][0]
    assert fixed.findtext("Payer") == "false" and float(fixed.findtext("FixedLegData/Rates/Rate")) == 0.02
    assert float(fixed.findtext("Notionals/Notional")) == 10_000_000


# --------------------------------------------------------------------------
# report_to_dataframe
# --------------------------------------------------------------------------


def test_report_to_dataframe_on_an_in_memory_report(ore):
    r = ore.InMemoryReport()
    r.addColumnSize("n").addColumnReal("x").addColumnString("s").addColumnDate("d").addColumnPeriod("p")
    r.nextRow()
    r.addSize(3).addReal(1.5).addString("a").addDate(ore.Date(5, ore.February, 2016)).addPeriod(
        ore.Period(6, ore.Months))
    r.nextRow()
    null_real = float(np.finfo(np.float32).max)  # QuantLib Null<Real>() -> "#N/A" in ORE's CSVs
    r.addSize(4).addReal(null_real).addString("").addDate(ore.Date()).addPeriod(ore.Period("1Y"))
    r.end()

    df = run_ore.report_to_dataframe(ore.PlainInMemoryReport(r))
    assert list(df.columns) == ["n", "x", "s", "d", "p"]
    assert list(df["n"]) == [3, 4]
    assert df["x"].iloc[0] == 1.5 and np.isnan(df["x"].iloc[1])
    assert list(df["s"]) == ["a", ""]
    assert pd.api.types.is_datetime64_any_dtype(df["d"])
    assert df["d"].iloc[0] == pd.Timestamp("2016-02-05") and pd.isna(df["d"].iloc[1])
    assert list(df["p"]) == ["6M", "1Y"]


# --------------------------------------------------------------------------
# path resolution
# --------------------------------------------------------------------------


def test_resolve_ore_xml_makes_paths_absolute_and_applies_overrides(tmp_path):
    out = tmp_path / "out"
    resolved = run_ore.resolve_ore_xml(INPUT, out, samples=7, market_configuration="xois_eur",
                                       active_analytics=["npv"])
    root = ET.parse(resolved).getroot()
    setup = _params(root.find("Setup"))
    assert Path(setup["inputPath"]) == INPUT.resolve()
    assert Path(setup["outputPath"]) == out.resolve()
    assert set(_params(root.find("Markets")).values()) == {"xois_eur"}
    a = _analytics(root)
    assert a["npv"]["active"] == "Y" and a["xva"]["active"] == "N"
    assert a["curves"]["configuration"] == "xois_eur"
    sim_file = (INPUT / a["simulation"]["simulationConfigFile"]).resolve()
    assert sim_file.is_file()
    assert ET.parse(sim_file).getroot().findtext("Parameters/Samples") == "7"
    # the checked-in input set is untouched
    assert ET.parse(INPUT / "simulation.xml").getroot().findtext("Parameters/Samples").strip() == "1000"


def test_unknown_market_configuration_is_rejected(tmp_path):
    """ORE would silently price under 'default' and we would label it 'foo'."""
    valid = run_ore.market_configurations(INPUT)
    assert valid == ["default", "collateral_inccy", "xois_eur", "xois_usd", "libor"]
    with pytest.raises(ValueError, match=r"unknown market configuration.*'foo'") as info:
        run_ore.run_exposure(INPUT, tmp_path / "out", market_configuration="foo")
    for cid in valid:  # the message lists the valid ids
        assert repr(cid) in str(info.value)
    assert not (tmp_path / "out").exists()  # rejected before anything was written
    with pytest.raises(SystemExit):  # the CLI refuses it too, before running ORE
        run_ore.main(["--market-config", "foo", "--results", str(tmp_path / "res")])
    assert not (tmp_path / "res").exists()


def test_run_tag_keeps_non_article_runs_off_the_canonical_names(tmp_path):
    assert run_ore.run_tag(INPUT) is None
    assert run_ore.run_tag(INPUT, "libor", 1000) is None
    assert run_ore.run_tag(INPUT, samples=16) == "libor_16"
    assert run_ore.run_tag(INPUT, "xois_eur") == "xois_eur_1000"
    other = tmp_path / "my_book"
    shutil.copytree(INPUT, other)
    assert run_ore.run_tag(other) == "my_book_libor_1000"
    assert run_ore.results_prefix({"input_dir": str(INPUT), "market_configuration": "libor",
                                   "samples": 1000}) == "risk_"
    assert run_ore.results_prefix({"input_dir": str(INPUT), "market_configuration": "xois_eur",
                                   "samples": 1000}) == "risk_xois_eur_1000_"


def test_pricing_curve_ids_follow_the_configuration():
    assert run_ore.pricing_curve_ids(INPUT, "libor") == ["EUR6M"]  # discounts AND projects
    assert run_ore.pricing_curve_ids(INPUT, "xois_eur") == ["EUR1D", "EUR6M"]
    with pytest.raises(ValueError, match="foo"):
        run_ore.pricing_curve_ids(INPUT, "foo")


def test_curve_pillars_from_a_calibration_report():
    rows = [  # long format as ORE's todaysmarketcalibration report (values are strings)
        ("yieldCurve", "C1", "dayCounter", "", "", "Actual/365 (Fixed)"),
        ("yieldCurve", "C1", "discountFactor", "2017-02-06", "SWAP/1Y", "0.99"),
        ("yieldCurve", "C1", "zeroRate", "2017-02-06", "SWAP/1Y", "0.01"),
        ("yieldCurve", "C1", "discountFactor", "2016-08-05", "MM/6M", "0.995"),
        ("yieldCurve", "C1", "zeroRate", "2016-08-05", "MM/6M", "0.01002"),
        ("yieldCurve", "C2", "discountFactor", "2017-02-06", "X", "0.5"),
        ("defaultCurve", "C1", "discountFactor", "2017-02-06", "X", "0.1"),
    ]
    cal = pd.DataFrame(rows, columns=["MarketObjectType", "MarketObjectId", "ResultId", "ResultKey1",
                                      "ResultKey2", "ResultValue"])
    p = run_ore.curve_pillars(cal, ["C1"])
    assert list(p.columns) == list(run_ore.CURVE_PILLARS_COLUMNS)
    assert list(p["date"]) == ["2016-08-05", "2017-02-06"]  # sorted, ISO
    assert list(p["discount_factor"]) == [0.995, 0.99]
    assert p["forward_rate"].isna().all()  # not in the report -> empty column, header kept
    both = run_ore.curve_pillars(cal, ["C2", "C1"])
    assert list(both["curve_id"]) == ["C2", "C1", "C1"]
    with pytest.raises(KeyError, match="C9"):
        run_ore.curve_pillars(cal, ["C9"])


# --------------------------------------------------------------------------
# ORE runs (small)
# --------------------------------------------------------------------------


def test_smoke_run_with_16_paths(smoke16, tmp_path):
    res = smoke16
    s = res["summary"]
    # the t0 NPV does not depend on the path count
    assert s["npv_base"] == pytest.approx(ARTICLE_NPV, abs=0.01)
    assert res["cube"] == {"ids": 1, "dates": 81, "samples": 16, "depth": 1}
    assert res["samples"] == 16 and res["market_configuration"] == "libor"
    assert s["cva"] > 0 and s["dva"] > 0
    assert list(s) == FLAT_KEYS  # the article summary layout
    assert set(run_ore.REPORTS) <= set(res["reports"])
    exp = res["reports"]["exposure_nettingset_CPTY_A"]
    assert {"Time", "EPE", "ENE", "PFE"} <= set(exp.columns)
    assert len(exp) == 82 and exp["Time"].iloc[0] == 0.0
    curves = res["reports"]["curves"]
    assert len(curves) == 240
    # under the "libor" configuration the EUR discount curve IS the EUR6M curve
    assert np.allclose(curves["EUR"], curves["EUR-EURIBOR-6M"])
    assert "EUR-EONIA" in curves.columns
    assert s["ore_version"].startswith("1.8")

    # native pillars of the pricing curve: ORE's 14 EUR6M instruments (6M deposit, 2Y..50Y swaps)
    p = res["curve_pillars"]
    assert list(p.columns) == list(run_ore.CURVE_PILLARS_COLUMNS)
    assert set(p["curve_id"]) == {"EUR6M"} and len(p) == 14
    assert p["date"].iloc[0] == "2016-08-09" and p["date"].iloc[-1] == "2066-02-09"
    assert "2036-02-11" in set(p["date"])  # the 20Y pillar just past the curves grid end
    assert p["date"].is_monotonic_increasing and p[["discount_factor", "zero_rate",
                                                     "forward_rate"]].notna().all().all()
    # the 240 x 1M curves report samples the same curve: its DF at the 10Y pillar date
    # lies between its two neighbouring grid points
    grid = curves.set_index(curves["Date"].dt.strftime("%Y-%m-%d"))["EUR"]
    df10 = float(p.loc[p["date"] == "2026-02-09", "discount_factor"].iloc[0])
    assert grid["2026-02-05"] > df10 > grid["2026-03-05"]

    # a 16-path run is not the article case: tagged file names, nothing canonical
    written = run_ore.write_results(res, tmp_path / "results")
    names = {Path(v).name for v in written.values()}
    assert names == {
        "risk_libor_16_exposure_nettingset.csv", "risk_libor_16_exposure_trade_Swap_20y.csv",
        "risk_libor_16_npv.csv", "risk_libor_16_xva.csv", "risk_libor_16_curves.csv",
        "risk_libor_16_cashflows.csv", "risk_libor_16_curve_pillars.csv",
        "risk_libor_16_exposure_profile.png", "risk_libor_16_summary.json",
    }
    assert all(Path(v).is_file() for v in written.values())
    assert not list((tmp_path / "results").glob("risk_summary.json"))
    back = pd.read_csv(written["curve_pillars"])
    assert list(back.columns) == list(run_ore.CURVE_PILLARS_COLUMNS)
    pd.testing.assert_frame_equal(back, p.reset_index(drop=True))


def _rename_trade(input_dir: Path, old: str, new: str) -> None:
    pf = input_dir / "portfolio_swap.xml"
    text = pf.read_text()
    assert text.count(f'id="{old}"') == 1
    pf.write_text(text.replace(f'id="{old}"', f'id="{new}"'))


def test_renamed_trade_is_discovered_not_hard_wired(staged_input, tmp_path, smoke16):
    """Trade id and netting set come from the npv report; the numbers do not change."""
    _rename_trade(staged_input, "Swap_20y", "IRS_EUR_Renamed")
    rc = run_ore.main(["--input", str(staged_input), "--samples", "16",
                       "--out", str(tmp_path / "out"), "--results", str(tmp_path / "res")])
    assert rc == 0
    prefix = "risk_input_libor_16_"  # custom input dir + libor + 16 paths
    s = json.loads((tmp_path / "res" / f"{prefix}summary.json").read_text())
    assert s["trade_id"] == "IRS_EUR_Renamed" and s["netting_set"] == "CPTY_A"
    assert list(s)[: len(FLAT_KEYS)] == FLAT_KEYS
    base = smoke16["summary"]
    for key in ("npv_base", "cva", "dva", "fba", "fca", "max_epe", "max_pfe", "max_ene"):
        assert s[key] == base[key], key  # same deterministic run, different label
    assert (tmp_path / "res" / f"{prefix}exposure_trade_IRS_EUR_Renamed.csv").is_file()
    assert (tmp_path / "res" / f"{prefix}exposure_nettingset.csv").is_file()
    assert (tmp_path / "res" / "figures" / f"{prefix}exposure_profile.png").is_file()
    assert "exposure_trade_IRS_EUR_Renamed" in s["files"]
    assert "Non-default run" in s["article_comparison"]["notes"][0]
    assert not (tmp_path / "res" / "risk_summary.json").exists()


def test_two_trades_in_two_netting_sets(staged_input, tmp_path, smoke16):
    """A second, identical swap in its own uncollateralised netting set CPTY_X."""
    pf = staged_input / "portfolio_swap.xml"
    root = ET.parse(pf).getroot()
    twin = ET.fromstring(ET.tostring(root.find("Trade")))
    twin.set("id", "Swap_20y_X")
    twin.find("Envelope/CounterParty").text = "CPTY_X"
    twin.find("Envelope/NettingSetId").text = "CPTY_X"
    root.append(twin)
    ET.ElementTree(root).write(pf)
    nt = staged_input / "netting.xml"
    nroot = ET.parse(nt).getroot()
    ns_x = ET.fromstring(ET.tostring(nroot.find("NettingSet")))  # CPTY_A: no CSA
    ns_x.find("NettingSetId").text = "CPTY_X"
    nroot.append(ns_x)
    ET.ElementTree(nroot).write(nt)
    tm = staged_input / "todaysmarket.xml"
    tm.write_text(tm.read_text().replace(
        '<DefaultCurve name="BANK">',
        '<DefaultCurve name="CPTY_X">Default/USD/CPTY_A_SR_USD</DefaultCurve>\n    <DefaultCurve name="BANK">', 1))

    res = run_ore.run_exposure(staged_input, tmp_path / "out", samples=16)
    s = res["summary"]
    assert s["trade_ids"] == ["Swap_20y", "Swap_20y_X"]
    assert s["netting_sets"] == ["CPTY_A", "CPTY_X"]
    assert "trade_id" not in s and "cva" not in s  # no single trade / netting set to flatten
    assert res["cube"]["ids"] == 2
    assert {"exposure_nettingset_CPTY_A", "exposure_nettingset_CPTY_X", "exposure_trade_Swap_20y",
            "exposure_trade_Swap_20y_X"} <= set(res["reports"])
    base = smoke16["summary"]
    assert s["npv_base"] == pytest.approx(2 * base["npv_base"], rel=1e-12)
    by_ns = s["by_netting_set"]
    for ns in ("CPTY_A", "CPTY_X"):
        assert by_ns[ns]["cva"] == pytest.approx(base["cva"], rel=1e-9), ns
        assert by_ns[ns]["max_epe"] == pytest.approx(base["max_epe"], rel=1e-6), ns
        assert by_ns[ns]["cva_pct_notional"] == pytest.approx(base["cva_pct_notional"], rel=1e-9)
    assert s["by_trade"]["Swap_20y_X"]["netting_set"] == "CPTY_X"
    assert s["by_trade"]["Swap_20y_X"]["npv_base"] == pytest.approx(base["npv_base"], rel=1e-12)

    written = run_ore.write_results(res, tmp_path / "res")
    names = {Path(v).name for v in written.values()}
    prefix = "risk_input_libor_16_"
    assert {f"{prefix}exposure_nettingset_CPTY_A.csv", f"{prefix}exposure_nettingset_CPTY_X.csv",
            f"{prefix}exposure_trade_Swap_20y.csv", f"{prefix}exposure_trade_Swap_20y_X.csv",
            f"{prefix}exposure_profile_CPTY_A.png", f"{prefix}exposure_profile_CPTY_X.png",
            f"{prefix}summary.json"} <= names
    assert f"{prefix}exposure_nettingset.csv" not in names


def test_renamed_pricing_engine_fails_loudly(staged_input, tmp_path):
    """The article's first failure mode: an engine name this wheel does not know.

    ORE's run() returns normally and getErrors() is empty; run_exposure must still fail.
    """
    pe = staged_input / "pricingengine.xml"
    pe.write_text(pe.read_text().replace("<Engine>DiscountingSwapEngine</Engine>",
                                         "<Engine>DiscountingSwapEngineOptimised</Engine>", 1))
    with pytest.raises(run_ore.OreRunError, match="DiscountingSwapEngineOptimised"):
        run_ore.run_exposure(staged_input, tmp_path / "out", active_analytics=["npv"])


def test_equity_book_is_parsed_but_not_priced_by_the_eur_demo_market(staged_input, tmp_path):
    pw.write_ore_portfolio(pw.demo_snapshot(), staged_input / "portfolio_swap.xml")
    with pytest.raises(run_ore.OreRunError, match="equity curve"):
        run_ore.run_exposure(staged_input, tmp_path / "out", active_analytics=["npv"])


# --------------------------------------------------------------------------
# positions -> ORE portfolio wire
# --------------------------------------------------------------------------


def _snapshot():
    return PositionSnapshot(
        as_of=date(2024, 6, 28),
        positions=[Position("AAPL", 100.0, 210.62), Position("BRK/B", -5.0, 406.8),
                   Position("MSFT", 0.0, 446.95)],
        cash=1000.0,
    )


def test_portfolio_writer_round_trip_through_ore(tmp_path, ore):
    snap = _snapshot()
    xml = pw.positions_to_ore_portfolio_xml(snap, counterparty="CPTY_A", netting_set="CPTY_A",
                                            currency="USD")
    trades = pw.parse_with_ore(xml=xml)
    assert len(trades) == len(snap.positions)
    assert {tt for _, tt in trades} == {"EquityPosition"}
    assert {tid for tid, _ in trades} == {"EQ_AAPL", "EQ_BRK_B", "EQ_MSFT"}

    path = pw.write_ore_portfolio(snap, tmp_path / "pf.xml")
    pf = ore.Portfolio()
    pf.fromFile(str(path))
    assert pf.size() == 3
    # what ORE writes back carries the same quantities and names
    back = ET.fromstring(pf.toXMLString())
    got = {t.get("id"): (float(t.findtext("EquityPositionData/Quantity")),
                         t.findtext("EquityPositionData/Underlying/Name"),
                         t.findtext("Envelope/NettingSetId"),
                         t.findtext("Envelope/AdditionalFields/currency"))
           for t in back.findall("Trade")}
    assert got["EQ_AAPL"] == (100.0, "AAPL", "CPTY_A", "USD")
    assert got["EQ_BRK_B"] == (-5.0, "BRK/B", "CPTY_A", "USD")


def test_portfolio_writer_from_positions_csv_and_options(tmp_path):
    snap = _snapshot()
    csv_path = write_positions_csv(snap, tmp_path / "positions.csv")
    assert "cash" in csv_path.read_text().splitlines()[0]  # the 6-column contract
    xml_path = pw.positions_csv_to_ore_portfolio(csv_path, tmp_path / "pf.xml", drop_flat=True)
    trades = pw.parse_with_ore(path=xml_path)
    assert sorted(tid for tid, _ in trades) == ["EQ_AAPL", "EQ_BRK_B"]
    # cash is not a trade: it is only noted in a comment, which ORE ignores
    text = xml_path.read_text()
    assert "Account cash 1000 is not a trade" in text
    assert len(ET.parse(xml_path).getroot().findall("Trade")) == 2
    # an old 5-column file (no cash column) still converts
    old = tmp_path / "old.csv"
    old.write_text("as_of,symbol,qty,last,value\n2024-06-28,AAPL,100.0,210.62,21062.0\n")
    assert [tid for tid, _ in pw.parse_with_ore(
        path=pw.positions_csv_to_ore_portfolio(old, tmp_path / "old.xml"))] == ["EQ_AAPL"]

    dup = PositionSnapshot(date(2024, 1, 2), [Position("A.B", 1, 1.0), Position("A/B", 1, 1.0)])
    dup_xml = pw.positions_to_ore_portfolio_xml(dup)  # "A.B" and "A/B" map to different ids
    assert len(pw.parse_with_ore(xml=dup_xml)) == 2
    with pytest.raises(ValueError, match="duplicate"):
        pw.positions_to_ore_portfolio_xml(
            PositionSnapshot(date(2024, 1, 2), [Position("X Y", 1, 1.0), Position("X_Y", 2, 1.0)]))


@pytest.mark.parametrize(
    "position, cash, message",
    [
        (Position("AAPL", math.nan, 210.0), 0.0, r"'AAPL'.*qty is not finite"),
        (Position("AAPL", math.inf, 210.0), 0.0, r"qty is not finite"),
        (Position("AAPL", 10.0, math.nan), 0.0, r"last price is not finite"),
        (Position("AAPL", 10.0, -math.inf), 0.0, r"last price is not finite"),
        (Position("AAPL", 1e200, 1e200), 0.0, r"market value .* not finite"),
        (Position("AAPL", "ten", 210.0), 0.0, r"qty is not a number"),
        (Position("", 10.0, 210.0), 0.0, r"symbol must be a non-empty string"),
        (Position("   ", 10.0, 210.0), 0.0, r"symbol must be a non-empty string"),
        (Position(None, 10.0, 210.0), 0.0, r"symbol must be a non-empty string"),
        (Position("AAPL", 10.0, 210.0), math.nan, r"cash is not finite"),
    ],
)
def test_portfolio_writer_rejects_invalid_positions(tmp_path, position, cash, message):
    snap = PositionSnapshot(date(2024, 6, 28), [Position("MSFT", 1.0, 400.0), position], cash=cash)
    with pytest.raises(ValueError, match=message):
        pw.positions_to_ore_portfolio_xml(snap)
    with pytest.raises(ValueError, match=message):
        pw.write_ore_portfolio(snap, tmp_path / "pf.xml")
    assert not (tmp_path / "pf.xml").exists()


def test_positions_csv_with_bad_rows_is_rejected(tmp_path):
    empty_symbol = tmp_path / "empty.csv"  # pandas alone would read this symbol as "nan"
    empty_symbol.write_text("as_of,symbol,qty,last,value,cash\n"
                            "2024-06-28,AAPL,100.0,210.62,21062.0,5.0\n"
                            "2024-06-28,,3.0,10.0,30.0,5.0\n")
    with pytest.raises(ValueError, match="line 3: empty symbol"):
        pw.positions_csv_to_ore_portfolio(empty_symbol, tmp_path / "pf.xml")
    nan_qty = tmp_path / "nan.csv"
    nan_qty.write_text("as_of,symbol,qty,last,value,cash\n2024-06-28,AAPL,,210.62,,5.0\n")
    with pytest.raises(ValueError, match="qty is not finite"):
        pw.positions_csv_to_ore_portfolio(nan_qty, tmp_path / "pf.xml")
    assert not (tmp_path / "pf.xml").exists()


# --------------------------------------------------------------------------
# committed results (written by `python -m quantstack.risk.run_ore`)
# --------------------------------------------------------------------------


@pytest.mark.skipif(not (RESULTS / "risk_summary.json").exists(),
                    reason="results/risk_summary.json not present (run python -m quantstack.risk.run_ore)")
def test_committed_results_files_exist():
    s = json.loads((RESULTS / "risk_summary.json").read_text())
    assert list(s)[: len(FLAT_KEYS)] == FLAT_KEYS
    assert s["market_configuration"] == "libor" and s["cube"]["samples"] == 1000
    expected = {
        "exposure_nettingset_CPTY_A": "results/risk_exposure_nettingset.csv",
        "exposure_trade_Swap_20y": "results/risk_exposure_trade_Swap_20y.csv",
        "npv": "results/risk_npv.csv",
        "xva": "results/risk_xva.csv",
        "curves": "results/risk_curves.csv",
        "cashflow": "results/risk_cashflows.csv",
        "curve_pillars": "results/risk_curve_pillars.csv",
        "figure": "results/figures/risk_exposure_profile.png",
    }
    assert s["files"] == expected
    for rel in expected.values():
        assert (run_ore.REPO_ROOT / rel).is_file(), rel

    # the bridge test reads this file: exact columns, ORE's 14 native EUR6M pillars
    p = pd.read_csv(RESULTS / "risk_curve_pillars.csv", dtype={"date": str})
    assert list(p.columns) == ["curve_id", "date", "discount_factor", "zero_rate", "forward_rate"]
    assert set(p["curve_id"]) == {"EUR6M"} and len(p) == 14
    assert all(date.fromisoformat(d).isoformat() == d for d in p["date"])
    assert p.loc[p["date"] == "2036-02-11", "discount_factor"].iloc[0] == pytest.approx(0.795041)


# --------------------------------------------------------------------------
# the full article run
# --------------------------------------------------------------------------


@pytest.mark.slow
def test_full_run_reproduces_the_article(tmp_path):
    res = run_ore.run_exposure(INPUT, tmp_path / "out")
    s = res["summary"]
    assert s["npv_base"] == pytest.approx(ARTICLE_NPV, abs=0.01)
    assert res["cube"] == {"ids": 1, "dates": 81, "samples": 1000, "depth": 1}
    assert s["cva"] > 0
    # regression anchor: the deterministic Sobol run reproduces the article's CVA
    assert s["cva"] == pytest.approx(107_446.98, rel=1e-3)
    exp = res["reports"]["exposure_nettingset_CPTY_A"]
    t, epe, pfe = exp["Time"].to_numpy(), exp["EPE"].to_numpy(), exp["PFE"].to_numpy()
    # hump: the peak is strictly inside the horizon and above both ends
    i = int(np.argmax(epe))
    assert 0.0 < t[i] < t[-1]
    assert epe[i] > epe[0] and epe[i] > epe[-1]
    j = int(np.argmax(pfe))
    assert 0.0 < t[j] < t[-1] and pfe[j] > 3 * pfe[0]
    assert epe[-1] == pytest.approx(0.0, abs=1.0)  # past maturity nothing is left
    assert list(s) == FLAT_KEYS
    assert len(res["curve_pillars"]) == 14
