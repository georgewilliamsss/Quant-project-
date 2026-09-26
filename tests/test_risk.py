"""Tests for quantstack.risk (ORE exposure/XVA run + positions -> ORE portfolio wire).

Fast tests (< ~10 s together) check the input set, the report conversion, the
path resolution, the portfolio writer against ORE's own parser, a 16-path smoke
run, and that ORE's *silent* failure modes are turned into loud errors.  The full
1000 x 81 reproduction of the article is marked ``slow``.
"""

from __future__ import annotations

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

ORE = pytest.importorskip("ORE")

INPUT = run_ore.DEFAULT_INPUT_DIR
ARTICLE_NPV = 1_609_885.84


def _params(elem):
    return {p.get("name"): (p.text or "").strip() for p in elem.findall("Parameter")}


def _analytics(root):
    return {a.get("type"): _params(a) for a in root.find("Analytics").findall("Analytic")}


@pytest.fixture()
def staged_input(tmp_path: Path) -> Path:
    """A private copy of the input set that a test may modify."""
    dst = tmp_path / "input"
    shutil.copytree(INPUT, dst)
    return dst


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


def test_report_to_dataframe_on_an_in_memory_report():
    r = ORE.InMemoryReport()
    r.addColumnSize("n").addColumnReal("x").addColumnString("s").addColumnDate("d").addColumnPeriod("p")
    r.nextRow()
    r.addSize(3).addReal(1.5).addString("a").addDate(ORE.Date(5, ORE.February, 2016)).addPeriod(
        ORE.Period(6, ORE.Months))
    r.nextRow()
    null_real = float(np.finfo(np.float32).max)  # QuantLib Null<Real>() -> "#N/A" in ORE's CSVs
    r.addSize(4).addReal(null_real).addString("").addDate(ORE.Date()).addPeriod(ORE.Period("1Y"))
    r.end()

    df = run_ore.report_to_dataframe(ORE.PlainInMemoryReport(r))
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


# --------------------------------------------------------------------------
# ORE runs (small)
# --------------------------------------------------------------------------


def test_smoke_run_with_16_paths(tmp_path):
    res = run_ore.run_exposure(INPUT, tmp_path / "out", samples=16)
    s = res["summary"]
    # the t0 NPV does not depend on the path count
    assert s["npv_base"] == pytest.approx(ARTICLE_NPV, abs=0.01)
    assert res["cube"] == {"ids": 1, "dates": 81, "samples": 16, "depth": 1}
    assert s["cva"] > 0 and s["dva"] > 0
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


def test_portfolio_writer_round_trip_through_ore(tmp_path):
    snap = _snapshot()
    xml = pw.positions_to_ore_portfolio_xml(snap, counterparty="CPTY_A", netting_set="CPTY_A",
                                            currency="USD")
    trades = pw.parse_with_ore(xml=xml)
    assert len(trades) == len(snap.positions)
    assert {tt for _, tt in trades} == {"EquityPosition"}
    assert {tid for tid, _ in trades} == {"EQ_AAPL", "EQ_BRK_B", "EQ_MSFT"}

    path = pw.write_ore_portfolio(snap, tmp_path / "pf.xml")
    pf = ORE.Portfolio()
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
    xml_path = pw.positions_csv_to_ore_portfolio(csv_path, tmp_path / "pf.xml", drop_flat=True)
    trades = pw.parse_with_ore(path=xml_path)
    assert sorted(tid for tid, _ in trades) == ["EQ_AAPL", "EQ_BRK_B"]

    dup = PositionSnapshot(date(2024, 1, 2), [Position("A.B", 1, 1.0), Position("A/B", 1, 1.0)])
    dup_xml = pw.positions_to_ore_portfolio_xml(dup)  # "A.B" and "A/B" map to different ids
    assert len(pw.parse_with_ore(xml=dup_xml)) == 2
    with pytest.raises(ValueError, match="duplicate"):
        pw.positions_to_ore_portfolio_xml(
            PositionSnapshot(date(2024, 1, 2), [Position("X Y", 1, 1.0), Position("X_Y", 2, 1.0)]))


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
