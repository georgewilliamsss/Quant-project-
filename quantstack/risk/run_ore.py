"""ORE in-process: exposure simulation + XVA for the article's 20y EUR swap.

Why this module exists
----------------------
The article ("Five Repos, One Engine") uses the Open Source Risk Engine for the
part of the stack that needs a *simulation of the future*: price the swap today,
evolve the market along 1000 Monte Carlo paths to 81 future dates, reprice the
swap on every (path, date), and turn that NPV cube into an exposure profile and
XVA.  "Python is just the ignition": all of that happens inside ORE's C++ code;
Python only points ``ORE.OREApp`` at an ``ore.xml`` and then pulls the results
back **in memory** (``OREApp.getReport`` / ``OREApp.getCube``), without parsing
the CSV files ORE also writes.

The case (trade ``Swap_20y`` in ``input/portfolio_swap.xml``): EUR 10M notional,
receive 2% fixed (30/360, annual, TARGET, Following) vs pay EUR-EURIBOR-6M
(A360, semi-annual, Modified Following), 2016-03-01 -> 2036-03-01, as-of
2016-02-05, counterparty and netting set ``CPTY_A`` (uncollateralised).

Inputs: a self-contained, reproducible set
------------------------------------------
``quantstack/risk/input`` holds every file the run needs (~600 kB).  All of them
come from the ORE repository at tag v1.8.16.0,
``Examples/ORE-Python/Notebooks/Example_9/Input``, except ``calendaradjustment.xml``
and ``currencies.xml`` (``Examples/Input``), which are passed explicitly so that
nothing is left to ORE's built-in defaults.  Deliberate edits carry a
``quantstack:`` comment in the XML.  The run is deterministic (Sobol +
Brownian bridge, seed 42).

Findings while building it (the "version-skew" notes)
-----------------------------------------------------
1. **Example_9 was never missing files.**  Its ``Input`` directory at v1.8.16.0
   *does* contain ``todaysmarket.xml``, ``pricingengine.xml`` and
   ``simulation.xml`` (all tracked in git), so the unmodified example did not fall
   back to defaults.  The CVA gap between Example_9's ExpectedOutput
   (101,160.81) and the article (107,446.98) is entirely the **path count**:
   Example_9's ``simulation.xml`` ships ``<Samples>100</Samples>``; the article ran
   1000.  With ``Samples=1000`` and nothing else changed, this wheel reproduces the
   article's CVA 107,446.98, EPE peak 1.707M and PFE95 peak 6.115M to the cent.
2. **The article's two failure modes do not occur with the v1.8.16.0 files and
   the 1.8.17.0 wheel.**
   * Renamed pricing engine: v1.8.16.0 ``pricingengine.xml`` uses
     ``DiscountingSwapEngine``.  ``DiscountingSwapEngineOptimised`` (the name the
     article met in master's files) does not occur anywhere in the 1.8.17.0
     ``_ORE`` binary.  If you use it anyway the failure is *silent* at the Python
     level: ``OREApp.run()`` returns normally, ``getErrors()`` is empty, the log
     says ``No EngineBuilder for DiscountedCashflows/DiscountingSwapEngineOptimised/Swap``
     and the ``npv`` report simply does not exist.  That is why
     :func:`run_exposure` checks for the expected reports and raises
     :class:`OreRunError` with the log's ALERT lines (see the test suite).
   * Missing overnight discount curves: v1.8.16.0 ``todaysmarket.xml`` defines
     the ``ois``/``xois_eur`` discounting curves (``Yield/EUR/EUR1D`` etc.) and
     the ``EUR-EONIA`` forwarding curve, so nothing is missing.
3. **Deprecated spellings.**  The 1.8.17.0 wheel accepts but warns about several
   v1.8.16.0 spellings (``LGM ccy=``, ``Extrapolation Y``,
   ``Parameters/Discretization``, ``SwaptionVolatilities/Currencies``,
   ``SwaptionVolatility currency=``).  They were replaced by the current
   equivalents; all numbers are bit-identical before and after.
4. **Shared ``Examples/Input`` files are not identical to Example_9's.**  Replacing
   ``market_20160205.txt``, ``conventions.xml``, ``curveconfig.xml``,
   ``todaysmarket.xml`` and ``pricingengine.xml`` by their v1.8.16.0
   ``Examples/Input`` versions gives NPV 1,609,885.88 (+0.05 EUR).  The files
   differ in thousands of lines (``RateCutoff`` in the conventions, market quotes,
   curve configs); the 0.05 EUR was not traced to one of them.  That combination
   runs in only two ways (1.8.17.0 wheel, measured):

   * without the ``curves`` analytic (npv, cashflow, simulation, xva active) and
     ``continueOnError=false``: NPV 1,609,885.88, CVA 107,446.98 at 1000 paths;
   * with every analytic of this ``ore.xml`` active and ``continueOnError=true``:
     NPV 1,609,885.88.

   With the ``curves`` analytic active and ``continueOnError=false`` (this
   ``ore.xml``) the run produces no ``npv`` report: the analytic builds every
   curve of the ``libor`` configuration, including ``Yield/EUR/EURBMB``, whose
   mandatory quote ``BOND/PRICE/SECURITY_2`` is not in that market file
   (:class:`OreRunError`).  Swapping in ``Examples/ORE-Python/Input/simulation.xml``
   as well (``Ordering=Steps``/``JoeKuoD7`` Sobol direction integers, CHF/JPY
   added; 1000 x 81, ``continueOnError=true``) moves CVA to 108,071.38 - same
   model, different quasi-random paths.  That simulation.xml does not run on
   Example_9's own files at all (they define no CHF/JPY curves; no ``xva``
   report).  Example_9's own files are the ones that reproduce the article exactly.

Market configuration
--------------------
``libor`` everywhere (single curve: EUR discounted *and* projected on
``Yield/EUR/EUR6M``), exactly as Example_9.  This reproduces the article's NPV
1,609,885.84.  The OIS-discounted alternative ``xois_eur`` (discount on
``Yield/EUR/EUR1D``, forward on EUR6M) is available through
``run_exposure(..., market_configuration="xois_eur")`` / ``--market-config``; it
changes every number (measured with this wheel, 1000 x 81: NPV 1,640,812.64,
CVA 110,909.34, DVA 77,443.25, FBA 35,205.12, FCA -16,538.46, EPE peak 1,742,215,
PFE95 peak 6,339,383).  It is not the default because the article - and the
QuantLib bridge test that checks the pricing module against ORE - use the
single-curve NPV 1,609,885.84.  The ``curves`` analytic reports under ``libor`` too, so column
``EUR`` of ``risk_curves.csv`` is the pricing discount curve (EUR6M); the OIS
curve is column ``EUR-EONIA``.  A configuration name that ``todaysmarket.xml``
does not define is rejected with ``ValueError``: ORE itself only records a
warning ("Configuration 'foo' not known ... Will retry with default
configuration") and prices under ``default`` - measured, ``foo`` returns the
``xois_eur`` NPV 1,640,812.64.

Outputs
-------
``results/risk_*`` (see :func:`write_results`): the in-memory ``npv``, ``xva``,
``curves`` and ``cashflow`` reports, one exposure CSV per netting set and per
trade (discovered from the ``npv`` report, not hard-wired), the exposure figure,
``risk_summary.json``, and ``risk_curve_pillars.csv``: ORE's *native* bootstrap
pillars of the pricing curve(s) (columns ``curve_id, date, discount_factor,
zero_rate, forward_rate``), taken from the in-memory ``todaysmarketcalibration``
report.  Under ``libor`` that is the 14-pillar ``Yield/EUR/EUR6M`` curve
(``curve_id`` ``EUR6M``), which both discounts EUR and projects
``EUR-EURIBOR-6M``.  ORE formats that report's values with 8 decimals, so the
pillar values carry 8 decimals too.

The canonical files are those of the article case (this input directory,
``libor``, 1000 paths).  Any other run - ``--samples``/``--market-config``/
``--input`` with values other than those, from the command line or as a
:func:`run_exposure` result passed to :func:`write_results` - is written under a
tagged prefix (``risk_<config>_<samples>_*``, e.g.
``results/risk_xois_eur_1000_summary.json``; see :func:`run_tag`) so it can
never overwrite them.

Numbers you should expect (1000 x 81, this wheel, this machine)
---------------------------------------------------------------
NPV 1,609,885.84; CVA 107,446.98; DVA 74,749.57; FBA 18,318.13;
FCA -58,081.34; EPE peak 1,707,220 at t = 1.00y; PFE95 peak 6,114,784;
cube 1 x 81 x 1000; ~7 s wall on 4 shared CPUs (article: 6.3 s).
The exposure at t=0 (1,608,755) is 0.07% below the NPV because the scenario
simulation market re-interpolates the curves on the simulation tenor grid
(3M ... 20Y, LogLinear) - it is not the pricing market.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parents[1]
DEFAULT_INPUT_DIR = MODULE_DIR / "input"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "results" / "ore_output"
DEFAULT_RESULTS_DIR = REPO_ROOT / "results"

#: The article case: its trade, netting set and notional (the summary and the
#: exposure reports themselves are discovered from the ``npv`` report).
TRADE_ID = "Swap_20y"
NETTING_SET = "CPTY_A"
NOTIONAL = 10_000_000.0

#: Reports pulled from ORE in memory for every run, whatever the portfolio.
STANDARD_REPORTS: tuple[str, ...] = ("npv", "xva", "curves", "cashflow", "todaysmarketcalibration")

#: The reports of the article case (name as in getReportNames()).  By default
#: :func:`run_exposure` pulls :data:`STANDARD_REPORTS` plus the
#: ``exposure_nettingset_<id>`` / ``exposure_trade_<id>`` reports of every
#: netting set and trade in the ``npv`` report, which for the article's input is
#: exactly this set.
REPORTS: tuple[str, ...] = (
    "npv",
    "xva",
    f"exposure_nettingset_{NETTING_SET}",
    f"exposure_trade_{TRADE_ID}",
    "curves",
    "cashflow",
    "todaysmarketcalibration",
)

#: Currency and index of the article trade: :func:`pricing_curve_ids` looks up the
#: curves that discount this currency and project this index.
PRICING_CURRENCY = "EUR"
PRICING_INDEX = "EUR-EURIBOR-6M"

#: Columns of ``risk_curve_pillars.csv`` (read by the bridge test).
CURVE_PILLARS_COLUMNS: tuple[str, ...] = ("curve_id", "date", "discount_factor", "zero_rate",
                                          "forward_rate")

#: The article's published numbers, for the comparison block of the summary.
ARTICLE = {
    "npv": 1_609_885.84,
    "cva": 107_446.98,
    "epe_peak": 1.71e6,
    "pfe95_peak": 6.11e6,
    "samples": 1000,
    "dates": 81,
    "wall_time_s": 6.3,
}

#: ``PlainInMemoryReport.columnType(i)`` codes (ore/OREData/ored/report/inmemoryreport.hpp;
#: the same mapping is used in ORE's own Examples/ORE-Python/ore.py).
COLUMN_TYPES = {0: "Size", 1: "Real", 2: "String", 3: "Date", 4: "Period"}

# QuantLib's Null<Real>() is numeric_limits<float>::max() (~3.4e38): ORE writes
# it as "#N/A" in CSV but hands it back as a number in memory.
_NULL_REAL_THRESHOLD = 1e37


class OreRunError(RuntimeError):
    """ORE finished without raising but did not produce what we asked for.

    ``OREApp.run()`` swallows trade-build and analytic failures (they go to the
    log as ALERT lines; ``getErrors()`` stays empty), so a misconfigured run looks
    like a successful one until you ask for a report.  This error carries the
    ALERT lines from the log so the cause is visible from Python.
    """


# --------------------------------------------------------------------------
# report -> DataFrame
# --------------------------------------------------------------------------


def _ore_date_to_timestamp(d) -> pd.Timestamp:
    # ORE's null Date() has serial number 0; everything else converts natively.
    if d.serialNumber() == 0:
        return pd.NaT
    return pd.Timestamp(d.to_date())


def report_to_dataframe(report) -> pd.DataFrame:
    """Convert an ORE ``PlainInMemoryReport`` into a pandas DataFrame.

    Generic over the five ORE column types: ``Size`` -> int64, ``Real`` ->
    float64 (QuantLib ``Null<Real>`` i.e. the CSV's ``#N/A`` -> NaN), ``String``
    -> object, ``Date`` -> datetime64 (null dates -> NaT), ``Period`` -> string
    such as ``"6M"``.  Reading column-wise (``dataAsReal(i)``) keeps it to one
    SWIG call per column instead of one per cell.
    """
    columns: dict[str, object] = {}
    for i in range(report.columns()):
        name = report.header(i)
        ctype = COLUMN_TYPES.get(report.columnType(i))
        if ctype == "Size":
            values = pd.array(list(report.dataAsSize(i)), dtype="Int64")
        elif ctype == "Real":
            arr = np.asarray(report.dataAsReal(i), dtype=float)
            arr[np.abs(arr) >= _NULL_REAL_THRESHOLD] = np.nan
            values = arr
        elif ctype == "String":
            values = list(report.dataAsString(i))
        elif ctype == "Date":
            values = pd.to_datetime([_ore_date_to_timestamp(d) for d in report.dataAsDate(i)])
        elif ctype == "Period":
            values = [str(p) for p in report.dataAsPeriod(i)]
        else:  # pragma: no cover - a new ORE column type
            raise TypeError(f"unknown ORE column type {report.columnType(i)} for {name!r}")
        if name in columns:  # ORE reports never do this, but do not lose data if one does
            name = f"{name}_{i}"
        columns[name] = values
    return pd.DataFrame(columns)


# --------------------------------------------------------------------------
# ore.xml resolution
# --------------------------------------------------------------------------


def _set_param(parent: ET.Element, name: str, value: str) -> None:
    for p in parent.findall("Parameter"):
        if p.get("name") == name:
            p.text = value
            return
    ET.SubElement(parent, "Parameter", {"name": name}).text = value


def _get_param(parent: ET.Element, name: str) -> str | None:
    for p in parent.findall("Parameter"):
        if p.get("name") == name:
            return (p.text or "").strip()
    return None


def _analytic(root: ET.Element, kind: str) -> ET.Element | None:
    for a in root.find("Analytics").findall("Analytic"):
        if a.get("type") == kind:
            return a
    return None


def _todaysmarket_path(input_dir: str | Path) -> Path:
    input_dir = Path(input_dir)
    setup = ET.parse(input_dir / "ore.xml").getroot().find("Setup")
    return input_dir / (_get_param(setup, "marketConfigFile") or "todaysmarket.xml")


def market_configurations(input_dir: str | Path = DEFAULT_INPUT_DIR) -> list[str]:
    """The ``<Configuration id=...>`` ids of the todaysmarket file ``ore.xml`` names.

    These are the only valid values for ``market_configuration``: ORE does not
    reject an unknown name, it silently prices under ``default`` instead.
    """
    root = ET.parse(_todaysmarket_path(input_dir)).getroot()
    return [c.get("id") for c in root.findall("Configuration") if c.get("id")]


def _check_market_configurations(root: ET.Element, input_dir: Path) -> None:
    """Raise ``ValueError`` if ``Markets`` or the curves analytic names an unknown configuration."""
    used = {f"Markets/{p.get('name')}": (p.text or "").strip() for p in root.find("Markets").findall("Parameter")}
    curves = _analytic(root, "curves")
    if curves is not None and _get_param(curves, "configuration"):
        used["curves/configuration"] = _get_param(curves, "configuration")
    valid = market_configurations(input_dir)
    bad = {k: v for k, v in used.items() if v not in valid}
    if bad:
        name = sorted(set(bad.values()))
        raise ValueError(
            f"unknown market configuration(s) {name} (used by {sorted(bad)}); "
            f"{_todaysmarket_path(input_dir).name} in {input_dir} defines: {valid}"
        )


def _simulation_samples(root: ET.Element, input_dir: Path) -> int | None:
    """Monte Carlo path count of the simulation config an ore.xml tree points at."""
    sim = _analytic(root, "simulation")
    name = _get_param(sim, "simulationConfigFile") if sim is not None else None
    if not name:
        return None
    node = ET.parse(input_dir / name).getroot().find("Parameters/Samples")
    return None if node is None else int((node.text or "").strip())


def _safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.\-]", "_", str(text))


def run_tag(
    input_dir: str | Path = DEFAULT_INPUT_DIR,
    market_configuration: str | None = None,
    samples: int | None = None,
) -> str | None:
    """``None`` for the article case, else a file-name tag such as ``"xois_eur_1000"``.

    The article case is: this module's input directory, market configuration
    ``libor`` and 1000 paths.  ``None`` arguments mean "as in the input's
    ``ore.xml`` / simulation config".  A different input directory adds its
    name in front (``"<dirname>_libor_16"``).
    """
    input_dir = Path(input_dir).resolve()
    root = ET.parse(input_dir / "ore.xml").getroot()
    config = market_configuration or _get_param(root.find("Markets"), "pricing")
    n = samples if samples is not None else _simulation_samples(root, input_dir)
    default_input = input_dir == DEFAULT_INPUT_DIR.resolve()
    if default_input and config == "libor" and n == ARTICLE["samples"]:
        return None
    parts = ([] if default_input else [input_dir.name]) + [str(config), str(n)]
    return "_".join(_safe_name(p) for p in parts)


def results_prefix(result: Mapping) -> str:
    """File-name prefix :func:`write_results` uses for ``result``: ``"risk_"`` only for the article case."""
    tag = run_tag(result["input_dir"], result.get("market_configuration"), result.get("samples"))
    return "risk_" if tag is None else f"risk_{tag}_"


def pricing_curve_ids(
    input_dir: str | Path = DEFAULT_INPUT_DIR,
    configuration: str = "libor",
    currency: str = PRICING_CURRENCY,
    index: str = PRICING_INDEX,
) -> list[str]:
    """Curve ids that discount ``currency`` and project ``index`` under ``configuration``.

    Read from the todaysmarket file: the configuration's ``DiscountingCurvesId``
    and ``IndexForwardingCurvesId`` (``default`` when absent, as in ORE) point at
    ``DiscountingCurve currency=...`` / ``Index name=...`` entries whose text is a
    curve spec ``Yield/<ccy>/<id>``; the ``<id>`` is what the
    ``todaysmarketcalibration`` report calls ``MarketObjectId``.  ``libor`` ->
    ``["EUR6M"]`` (one curve does both), ``xois_eur`` -> ``["EUR1D", "EUR6M"]``.
    """
    root = ET.parse(_todaysmarket_path(input_dir)).getroot()
    conf = next((c for c in root.findall("Configuration") if c.get("id") == configuration), None)
    if conf is None:
        raise ValueError(f"no market configuration {configuration!r}; "
                         f"defined: {market_configurations(input_dir)}")

    def lookup(group_tag: str, id_tag: str, item_tag: str, attr: str, key: str) -> str | None:
        group_id = (conf.findtext(id_tag) or "default").strip()
        for group in root.findall(group_tag):
            if group.get("id") == group_id:
                for item in group.findall(item_tag):
                    if item.get(attr) == key and item.text:
                        return item.text.strip().split("/")[-1]
        return None

    ids = [lookup("DiscountingCurves", "DiscountingCurvesId", "DiscountingCurve", "currency", currency),
           lookup("IndexForwardingCurves", "IndexForwardingCurvesId", "Index", "name", index)]
    return list(dict.fromkeys(i for i in ids if i))


def curve_pillars(calibration: pd.DataFrame, curve_ids: Iterable[str]) -> pd.DataFrame:
    """Native pillars of ORE yield curves from a ``todaysmarketcalibration`` report.

    The report is long format (one row per ``MarketObjectId`` x ``ResultId`` x
    pillar date ``ResultKey1`` x instrument ``ResultKey2``; values as strings).
    Returns one row per pillar with :data:`CURVE_PILLARS_COLUMNS`, curves in the
    order given, dates ascending and ISO-formatted; a result the report lacks
    (e.g. ``forwardRate``) becomes a NaN column, i.e. an empty CSV field.
    """
    key1 = calibration["ResultKey1"].fillna("").astype(str).str.strip()
    frames = []
    for cid in curve_ids:
        sel = calibration[(calibration["MarketObjectType"] == "yieldCurve")
                          & (calibration["MarketObjectId"] == cid) & (key1 != "")].copy()
        if sel.empty:
            raise KeyError(f"todaysmarketcalibration report has no pillars for yield curve {cid!r}")
        sel["ResultKey1"] = key1[sel.index]
        sel["value"] = pd.to_numeric(sel["ResultValue"], errors="coerce")
        # one row per (pillar date, instrument) that the report has; a missing
        # ResultId for one pillar stays NaN
        wide = (sel.groupby(["ResultKey1", "ResultKey2", "ResultId"], sort=True)["value"].first()
                .unstack("ResultId").reset_index())
        col = lambda name: (wide[name].astype(float) if name in wide.columns  # noqa: E731
                            else pd.Series(np.nan, index=wide.index))
        frames.append(pd.DataFrame({
            "curve_id": cid,
            "date": [pd.Timestamp(d).date().isoformat() for d in wide["ResultKey1"]],
            "discount_factor": col("discountFactor"),
            "zero_rate": col("zeroRate"),
            "forward_rate": col("forwardRate"),
        }).sort_values("date", kind="stable"))
    if not frames:
        return pd.DataFrame(columns=list(CURVE_PILLARS_COLUMNS))
    return pd.concat(frames, ignore_index=True)[list(CURVE_PILLARS_COLUMNS)]


def referenced_input_files(ore_xml: str | Path) -> list[str]:
    """Every input file name an ``ore.xml`` points at (relative to inputPath).

    Used by the tests to prove the input directory is self-contained.
    """
    root = ET.parse(ore_xml).getroot()
    setup_keys = (
        "marketDataFile", "fixingDataFile", "dividendDataFile", "curveConfigFile",
        "conventionsFile", "marketConfigFile", "pricingEnginesFile", "portfolioFile",
        "calendarAdjustment", "currencyConfiguration", "referenceDataFile",
        "iborFallbackConfig", "scriptLibrary",
    )
    files: list[str] = []
    setup = root.find("Setup")
    for key in setup_keys:
        v = _get_param(setup, key)
        if v:
            files.append(v)
    input_keys = {"simulationConfigFile", "pricingEnginesFile", "csaFile", "sensitivityConfigFile",
                  "scenarioConfigFile", "stressConfigFile"}
    for a in root.find("Analytics").findall("Analytic"):
        if _get_param(a, "active") != "Y":
            continue
        for p in a.findall("Parameter"):
            if p.get("name") in input_keys and (p.text or "").strip():
                files.append(p.text.strip())
    # de-duplicate, keep order
    return list(dict.fromkeys(files))


def resolve_ore_xml(
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    samples: int | None = None,
    market_configuration: str | None = None,
    active_analytics: Iterable[str] | None = None,
    log_mask: int | None = None,
) -> Path:
    """Write ``output_dir/ore_resolved.xml``: the input ore.xml with absolute paths.

    ORE resolves ``inputPath``/``outputPath`` against the *process* CWD.  Changing
    the CWD from a library is a process-global side effect (and breaks under
    threads/pytest), so instead we rewrite both paths to absolute ones in a
    generated copy.  Optional overrides, all applied only to the copy:

    * ``samples`` - write a copy of simulation.xml with a different path count
      (used by the fast tests); referenced via a path relative to inputPath
      because ORE joins ``inputPath + "/" + file``.
    * ``market_configuration`` - use this todaysmarket configuration for every
      Markets entry and for the curves report (e.g. ``"xois_eur"``).
    * ``active_analytics`` - keep only these Analytic types active.

    Every configuration the resolved file uses must be a ``<Configuration id>``
    of the input's todaysmarket file, otherwise ``ValueError`` (listing the
    valid ids) is raised before anything is written.
    """
    input_dir = Path(input_dir).resolve()
    output_dir = Path(output_dir).resolve()
    tree = ET.parse(input_dir / "ore.xml")
    root = tree.getroot()
    setup = root.find("Setup")
    _set_param(setup, "inputPath", str(input_dir))
    _set_param(setup, "outputPath", str(output_dir))
    if log_mask is not None:
        _set_param(setup, "logMask", str(int(log_mask)))

    if market_configuration:
        for p in root.find("Markets").findall("Parameter"):
            p.text = market_configuration
        curves = _analytic(root, "curves")
        if curves is not None:
            _set_param(curves, "configuration", market_configuration)

    if active_analytics is not None:
        keep = set(active_analytics)
        for a in root.find("Analytics").findall("Analytic"):
            _set_param(a, "active", "Y" if a.get("type") in keep else "N")

    _check_market_configurations(root, input_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if samples is not None:
        sim = _analytic(root, "simulation")
        sim_name = _get_param(sim, "simulationConfigFile")
        sim_tree = ET.parse(input_dir / sim_name)
        node = sim_tree.getroot().find("Parameters/Samples")
        node.text = str(int(samples))
        override = output_dir / f"simulation_samples{int(samples)}.xml"
        sim_tree.write(override, xml_declaration=True, encoding="utf-8")
        _set_param(sim, "simulationConfigFile", os.path.relpath(override, input_dir))

    resolved = output_dir / "ore_resolved.xml"
    root.insert(0, ET.Comment(" generated by quantstack.risk.run_ore from "
                              f"{input_dir / 'ore.xml'} - do not edit "))
    tree.write(resolved, xml_declaration=True, encoding="utf-8")
    return resolved


def _log_alerts(output_dir: Path, log_name: str = "log.txt", limit: int = 10) -> list[str]:
    log = output_dir / log_name
    if not log.exists():
        return []
    lines = [ln.strip() for ln in log.read_text(errors="replace").splitlines()
             if ln.startswith("ALERT") or ln.startswith("CRITICAL")]
    return lines[:limit]


# --------------------------------------------------------------------------
# the run
# --------------------------------------------------------------------------


def run_exposure(
    input_dir: str | Path = DEFAULT_INPUT_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    *,
    samples: int | None = None,
    market_configuration: str | None = None,
    active_analytics: Iterable[str] | None = None,
    reports: Iterable[str] | None = None,
) -> dict:
    """Run ORE in-process on ``input_dir`` and return results as DataFrames.

    ``reports=None`` (the default) pulls :data:`STANDARD_REPORTS` plus, for every
    trade and netting set in the ``npv`` report, ``exposure_trade_<id>`` and
    ``exposure_nettingset_<id>`` (see :func:`exposure_report_names`); an explicit
    list pulls those names (plus ``npv``, which the summary needs).  Returns a
    dict with keys

    * ``reports``: ``{report name: DataFrame}`` for every requested report that
      the run produced (via :func:`report_to_dataframe`);
    * ``cube``: ``{"ids", "dates", "samples", "depth"}`` of the NPV cube, read
      with ``OREApp.getCube("cube")`` (only when the simulation analytic ran);
    * ``curve_pillars``: ORE's native pillars of the pricing curve(s)
      (:func:`curve_pillars` of the ``todaysmarketcalibration`` report for
      :func:`pricing_curve_ids`), or ``None`` if that report was not pulled;
    * ``summary``: the key numbers (see :func:`summarise`);
    * ``wall_time_s``: wall-clock seconds of ``OREApp`` construction + ``run()``;
    * ``ore_version``, ``resolved_ore_xml``, ``input_dir``, ``output_dir``,
      ``report_names``, ``market_configuration`` (the pricing one), ``samples``
      (the simulation config's path count, whether or not the simulation ran).

    Raises ``ValueError`` for a market configuration the input's todaysmarket
    file does not define, and :class:`OreRunError` if ORE did not produce the
    ``npv`` report (or, when the xva analytic is active, the ``xva`` report),
    with the log's ALERT lines.  ORE's log is closed whatever happens.
    """
    import ORE  # heavy import kept local so that `import quantstack.risk` stays cheap

    input_dir = Path(input_dir).resolve()
    output_dir = Path(output_dir).resolve()
    resolved = resolve_ore_xml(
        input_dir, output_dir,
        samples=samples,
        market_configuration=market_configuration,
        active_analytics=active_analytics,
    )
    root = ET.parse(resolved).getroot()
    active = {a.get("type") for a in root.find("Analytics").findall("Analytic")
              if _get_param(a, "active") == "Y"}
    pricing_config = _get_param(root.find("Markets"), "pricing")

    params = ORE.Parameters()
    params.fromFile(str(resolved))
    t0 = time.perf_counter()
    app = ORE.OREApp(params, False)
    try:
        app.run()
        wall = time.perf_counter() - t0
        names = set(app.getReportNames())
        required = ["npv"] + (["xva"] if "xva" in active else [])
        missing = [r for r in required if r not in names]
        errors = list(app.getErrors())
        frames: dict[str, pd.DataFrame] = {}
        cube_info = None
        if not missing:
            frames["npv"] = report_to_dataframe(app.getReport("npv"))
            if reports is None:
                wanted = list(STANDARD_REPORTS) + exposure_report_names(frames["npv"])
            else:
                wanted = list(reports)
            for name in wanted:
                if name in names and name not in frames:
                    frames[name] = report_to_dataframe(app.getReport(name))
            if "cube" in set(app.getCubeNames()):
                cube = app.getCube("cube")
                cube_info = {
                    "ids": int(cube.numIds()),
                    "dates": int(cube.numDates()),
                    "samples": int(cube.samples()),
                    "depth": int(cube.depth()),
                }
        version = app.version()
    finally:
        app.closeLog()  # flushes log.txt (read below on failure); ORE's logger is not ours otherwise
    del app

    if missing:
        raise OreRunError(
            f"ORE run on {resolved} produced no {missing} report(s). "
            f"getErrors()={errors!r}. Log ALERT lines:\n" + "\n".join(_log_alerts(output_dir))
        )

    pillars = None
    if "todaysmarketcalibration" in frames:
        pillars = curve_pillars(frames["todaysmarketcalibration"],
                                pricing_curve_ids(input_dir, pricing_config))

    result = {
        "reports": frames,
        "cube": cube_info,
        "curve_pillars": pillars,
        "wall_time_s": wall,
        "ore_version": version,
        "resolved_ore_xml": str(resolved),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "report_names": sorted(names),
        "market_configuration": pricing_config,
        "samples": _simulation_samples(root, input_dir),
    }
    result["summary"] = summarise(result)
    return result


def trades_and_netting_sets(npv: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Trade ids and netting set ids of an ``npv`` report, in report order (no duplicates)."""
    trades = list(dict.fromkeys(str(t) for t in npv["TradeId"]))
    netting_sets = list(dict.fromkeys(str(n) for n in npv["NettingSet"] if str(n)))
    return trades, netting_sets


def exposure_report_names(npv: pd.DataFrame) -> list[str]:
    """``exposure_nettingset_<id>`` for every netting set, then ``exposure_trade_<id>`` per trade."""
    trades, netting_sets = trades_and_netting_sets(npv)
    return [f"exposure_nettingset_{n}" for n in netting_sets] + [f"exposure_trade_{t}" for t in trades]


def _num(x) -> float | None:
    x = float(x)
    return None if math.isnan(x) else x


def _exposure_summary(e: pd.DataFrame) -> dict:
    i_epe = int(e["EPE"].idxmax())
    i_pfe = int(e["PFE"].idxmax())
    i_ene = int(e["ENE"].idxmax())
    return {
        "exposure_rows": int(len(e)),
        "exposure_future_dates": int((e["Time"] > 0).sum()),
        "horizon_years": float(e["Time"].max()),
        "epe_t0": float(e["EPE"].iloc[0]),
        "max_epe": float(e["EPE"].iloc[i_epe]),
        "max_epe_time_years": float(e["Time"].iloc[i_epe]),
        "max_epe_date": e["Date"].iloc[i_epe].date().isoformat(),
        "max_ene": float(e["ENE"].iloc[i_ene]),
        "max_ene_time_years": float(e["Time"].iloc[i_ene]),
        "max_pfe": float(e["PFE"].iloc[i_pfe]),
        "max_pfe_time_years": float(e["Time"].iloc[i_pfe]),
    }


def _netting_set_summary(frames: Mapping[str, pd.DataFrame], netting_set: str) -> dict:
    """XVA + exposure numbers of one netting set (keys as in the article summary)."""
    s: dict = {}
    npv = frames["npv"]
    if "xva" in frames:
        xva = frames["xva"]
        rows = xva.loc[(xva["TradeId"] == "") & (xva["NettingSetId"] == netting_set)]
        if len(rows):
            ns = rows.iloc[0]
            for col in ("CVA", "DVA", "FBA", "FCA", "BaselEPE", "BaselEEPE"):
                s[col.lower() if col.isupper() else col] = _num(ns[col])
            if s["fba"] is not None and s["fca"] is not None:
                s["fva"] = s["fba"] + s["fca"]  # ORE sign convention: FBA >= 0 benefit, FCA <= 0 cost
            # gross notional of the netting set's trades (the article trade: 10M)
            notional = float(npv.loc[npv["NettingSet"] == netting_set, "Notional(Base)"].sum())
            ok = s["cva"] is not None and math.isfinite(notional) and notional > 0
            s["cva_pct_notional"] = 100.0 * s["cva"] / notional if ok else None
    exp_name = f"exposure_nettingset_{netting_set}"
    if exp_name in frames:
        s.update(_exposure_summary(frames[exp_name]))
    return s


def summarise(result: Mapping) -> dict:
    """Key numbers of a :func:`run_exposure` result, JSON-serialisable.

    Trades and netting sets come from the ``npv`` report.  With one trade in one
    netting set (the article case) the summary is flat: ``trade_id``,
    ``netting_set``, ``npv_base``, ``cva`` ... ``max_pfe_time_years``.  With
    several trades it carries ``trade_ids``, ``npv_base`` = the sum of
    ``NPV(Base)`` and ``by_trade`` (per-trade NPV, CVA and exposure peaks); with
    several netting sets ``netting_sets`` and ``by_netting_set`` (per netting set
    the same XVA/exposure keys as the flat case) instead of flat XVA keys.
    """
    frames = result["reports"]
    npv = frames["npv"]
    trades, netting_sets = trades_and_netting_sets(npv)
    s: dict = {
        "ore_version": result["ore_version"],
        "wall_time_s": round(float(result["wall_time_s"]), 3),
        "market_configuration": result.get("market_configuration"),
    }
    if len(trades) == 1:
        s["trade_id"] = trades[0]
    else:
        s["trade_ids"] = trades
    if len(netting_sets) == 1:
        s["netting_set"] = netting_sets[0]
    else:
        s["netting_sets"] = netting_sets
    s["cube"] = result.get("cube")

    if len(trades) == 1:
        row = npv.loc[npv["TradeId"] == trades[0]].iloc[0]
        s["npv_base"] = float(row["NPV(Base)"])
        s["npv_currency"] = str(row["BaseCurrency"])
    else:
        s["npv_base"] = float(npv["NPV(Base)"].sum())
        s["npv_currency"] = "/".join(dict.fromkeys(str(c) for c in npv["BaseCurrency"]))

    if len(netting_sets) == 1:
        s.update(_netting_set_summary(frames, netting_sets[0]))
    else:
        s["by_netting_set"] = {n: _netting_set_summary(frames, n) for n in netting_sets}

    if len(trades) > 1:
        by_trade: dict = {}
        xva = frames.get("xva")
        for tid in trades:
            row = npv.loc[npv["TradeId"] == tid].iloc[0]
            t = {
                "netting_set": str(row["NettingSet"]),
                "npv_base": float(row["NPV(Base)"]),
                "notional_base": _num(row["Notional(Base)"]),
            }
            if xva is not None:
                xrow = xva.loc[xva["TradeId"] == tid]
                if len(xrow):
                    t["cva"] = _num(xrow.iloc[0]["CVA"])
            exp_name = f"exposure_trade_{tid}"
            if exp_name in frames:
                e = _exposure_summary(frames[exp_name])
                t.update({k: e[k] for k in ("max_epe", "max_epe_time_years", "max_pfe",
                                            "max_pfe_time_years")})
            by_trade[tid] = t
        s["by_trade"] = by_trade
    return s


def _is_article_portfolio(summary: Mapping) -> bool:
    return summary.get("trade_id") == TRADE_ID and summary.get("netting_set") == NETTING_SET


def compare_to_article(summary: Mapping) -> dict:
    """Side-by-side with the article's numbers; differences are reported, never tuned."""
    out: dict = {"article": dict(ARTICLE)}
    pairs = {
        "npv": summary.get("npv_base"),
        "cva": summary.get("cva"),
        "epe_peak": summary.get("max_epe"),
        "pfe95_peak": summary.get("max_pfe"),
        "wall_time_s": summary.get("wall_time_s"),
    }
    cube = summary.get("cube") or {}
    pairs["samples"] = cube.get("samples")
    pairs["dates"] = cube.get("dates")
    out["ours"] = pairs
    out["abs_diff"] = {k: (None if v is None else float(v) - float(ARTICLE[k])) for k, v in pairs.items()}
    if (summary.get("market_configuration") != "libor" or cube.get("samples") != ARTICLE["samples"]
            or not _is_article_portfolio(summary)):
        trades = summary.get("trade_ids") or [summary.get("trade_id")]
        out["notes"] = [
            f"Non-default run (market configuration {summary.get('market_configuration')!r}, "
            f"{cube.get('samples')} paths, trades {trades}): differences from the article are "
            f"expected; the article case is trade {TRADE_ID!r} in netting set {NETTING_SET!r}, "
            "market configuration 'libor', 1000 paths.",
        ]
        return out
    out["notes"] = [
        "Inputs: ORE v1.8.16.0 Example_9 files with simulation Samples=1000 (Example_9 ships 100), "
        "ORE wheel 1.8.17.0.",
        "NPV and CVA match the article to the cent: the article ran the same Example_9 inputs at 1000 paths.",
        "The article's EPE/PFE peaks are quoted rounded (1.71M / 6.11M); ours are the unrounded values.",
        "Example_9's ExpectedOutput CVA 101,160.81 is the same setup at 100 paths, not a defaults fallback.",
        "Wall time depends on the machine and on concurrent load (4 shared CPUs here).",
    ]
    return out


# --------------------------------------------------------------------------
# results files + figure
# --------------------------------------------------------------------------


def _for_csv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%d")
    return out


#: Title of the article's exposure figure (one trade, netting set CPTY_A).
ARTICLE_PLOT_TITLE = "Exposure profile, netting set CPTY_A: 20y EUR IRS, receive 2% fixed, 10M"


def write_results(
    result: Mapping,
    results_dir: str | Path = DEFAULT_RESULTS_DIR,
    *,
    prefix: str | None = None,
) -> dict[str, str]:
    """Write the results files of a :func:`run_exposure` result; return ``{key: path}``.

    ``prefix=None`` means :func:`results_prefix`: ``"risk_"`` for the article
    case (this module's input, ``libor``, 1000 paths), ``"risk_<tag>_"`` for any
    other run, so that a non-article run never overwrites the canonical files.
    With prefix ``risk_`` the files are:

    * ``risk_npv.csv``, ``risk_xva.csv``, ``risk_curves.csv``,
      ``risk_cashflows.csv`` - the in-memory reports, full float precision;
    * ``risk_exposure_nettingset.csv`` (one netting set) or
      ``risk_exposure_nettingset_<id>.csv`` (several), and
      ``risk_exposure_trade_<id>.csv`` for every trade;
    * ``risk_curve_pillars.csv`` - native pillars of the pricing curve(s),
      columns :data:`CURVE_PILLARS_COLUMNS`;
    * ``risk_summary.json`` - :func:`summarise` + article comparison + inputs + files;
    * ``figures/risk_exposure_profile.png`` (or ``..._<netting set>.png`` per
      netting set when there are several).
    """
    results_dir = Path(results_dir)
    if prefix is None:
        prefix = results_prefix(result)
    (results_dir / "figures").mkdir(parents=True, exist_ok=True)
    frames = result["reports"]
    npv = frames["npv"]
    written: dict[str, str] = {}

    ns_key, trade_key = "exposure_nettingset_", "exposure_trade_"
    ns_reports = [n for n in frames if n.startswith(ns_key)]
    trade_reports = [n for n in frames if n.startswith(trade_key)]
    mapping: dict[str, str] = {}
    for name in ns_reports:
        mapping[name] = (f"{prefix}exposure_nettingset.csv" if len(ns_reports) == 1
                         else f"{prefix}exposure_nettingset_{_safe_name(name[len(ns_key):])}.csv")
    for name in trade_reports:
        mapping[name] = f"{prefix}exposure_trade_{_safe_name(name[len(trade_key):])}.csv"
    mapping.update({
        "npv": f"{prefix}npv.csv",
        "xva": f"{prefix}xva.csv",
        "curves": f"{prefix}curves.csv",
        "cashflow": f"{prefix}cashflows.csv",
    })
    for report, fname in mapping.items():
        if report in frames:
            path = results_dir / fname
            _for_csv(frames[report]).to_csv(path, index=False)  # full float precision (bridge test)
            written[report] = str(path)

    pillars = result.get("curve_pillars")
    if pillars is not None and len(pillars):
        path = results_dir / f"{prefix}curve_pillars.csv"
        pillars[list(CURVE_PILLARS_COLUMNS)].to_csv(path, index=False)
        written["curve_pillars"] = str(path)

    summary = dict(result["summary"])
    summary["article_comparison"] = compare_to_article(summary)
    default_input = Path(result["input_dir"]).resolve() == DEFAULT_INPUT_DIR.resolve()
    summary["inputs"] = {
        "input_dir": os.path.relpath(result["input_dir"], REPO_ROOT),
        "source": ("ORE v1.8.16.0 Examples/ORE-Python/Notebooks/Example_9/Input (+ Examples/Input "
                   "calendaradjustment.xml, currencies.xml); simulation Samples 100 -> 1000")
        if default_input else "user-supplied input directory (not the article's input set)",
        "resolved_ore_xml": os.path.relpath(result["resolved_ore_xml"], REPO_ROOT),
        "curves_report_configuration": summary.get("market_configuration"),
        "curves_report_columns": "EUR = discount curve of that configuration (EUR6M under 'libor', "
                                 "EUR1D under 'xois_eur'); EUR-EURIBOR-6M = 6M projection curve; "
                                 "EUR-EONIA = OIS curve EUR1D",
    }
    summary["files"] = {k: os.path.relpath(v, REPO_ROOT) for k, v in written.items()}

    for name in ns_reports:
        ns = name[len(ns_key):]
        single = len(ns_reports) == 1
        fig_path = results_dir / "figures" / (f"{prefix}exposure_profile.png" if single
                                              else f"{prefix}exposure_profile_{_safe_name(ns)}.png")
        ns_trades = [str(t) for t in npv.loc[npv["NettingSet"] == ns, "TradeId"]]
        if single and _is_article_portfolio(summary):
            title, plot_summary = ARTICLE_PLOT_TITLE, summary
        else:
            shown = ", ".join(ns_trades[:3]) + (", ..." if len(ns_trades) > 3 else "")
            title = f"Exposure profile, netting set {ns}: {len(ns_trades)} trade(s) ({shown})"
            ns_numbers = summary if single else summary["by_netting_set"][ns]
            plot_summary = {
                "npv_base": float(npv.loc[npv["NettingSet"] == ns, "NPV(Base)"].sum()),
                "cva": ns_numbers.get("cva") if ns_numbers.get("cva") is not None else float("nan"),
                "cube": summary.get("cube"),
                "ore_version": summary.get("ore_version"),
            }
        plot_exposure(frames[name], fig_path, plot_summary, title=title)
        key = "figure" if single else f"figure_{ns}"
        summary["files"][key] = os.path.relpath(fig_path, REPO_ROOT)
        written[key] = str(fig_path)
    json_path = results_dir / f"{prefix}summary.json"
    json_path.write_text(json.dumps(summary, indent=2, default=str) + "\n")
    written["summary"] = str(json_path)
    return written


def plot_exposure(
    exposure: pd.DataFrame,
    path: str | Path,
    summary: Mapping | None = None,
    *,
    title: str | None = None,
) -> Path:
    """EPE / ENE / PFE95 against time: the classic uncollateralised-swap profile.

    ``title`` defaults to the article's (:data:`ARTICLE_PLOT_TITLE`).
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, ink2, grid, surface = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    c_epe, c_ene, c_pfe = "#2a78d6", "#eb6834", "#1baf7a"  # categorical slots 1-3

    t = exposure["Time"].to_numpy()
    epe = exposure["EPE"].to_numpy() / 1e6
    ene = exposure["ENE"].to_numpy() / 1e6
    pfe = exposure["PFE"].to_numpy() / 1e6

    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=110)
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)
    ax.plot(t, pfe, color=c_pfe, lw=2, label="PFE 95%")
    ax.plot(t, epe, color=c_epe, lw=2, label="EPE")
    ax.plot(t, -ene, color=c_ene, lw=2, label="ENE (plotted negative)")
    ax.axhline(0, color=ink2, lw=0.8)

    i = int(np.argmax(epe))
    ax.plot([t[i]], [epe[i]], "o", ms=8, color=c_epe, mec=surface, mew=2, zorder=5)
    ax.annotate(f"EPE peak {epe[i]:.2f}M at {t[i]:.1f}y", (t[i], epe[i]), xytext=(22, 26),
                textcoords="offset points", color=ink, fontsize=9,
                arrowprops=dict(arrowstyle="-", color=ink2, lw=0.8))
    j = int(np.argmax(pfe))
    ax.plot([t[j]], [pfe[j]], "o", ms=8, color=c_pfe, mec=surface, mew=2, zorder=5)
    ax.annotate(f"PFE95 peak {pfe[j]:.2f}M at {t[j]:.1f}y", (t[j], pfe[j]), xytext=(14, 8),
                textcoords="offset points", color=ink, fontsize=9)

    n_paths = (summary or {}).get("cube", {}) or {}
    sub = ""
    if summary:
        sub = (f"NPV {summary.get('npv_base', float('nan')):,.0f} EUR   "
               f"CVA {summary.get('cva', float('nan')):,.0f}   "
               f"{n_paths.get('samples', '?')} paths x {n_paths.get('dates', '?')} dates   "
               f"ORE {summary.get('ore_version', '')}")
    ax.set_title(ARTICLE_PLOT_TITLE if title is None else title,
                 color=ink, fontsize=11, loc="left", pad=22)
    ax.text(0, 1.02, sub, transform=ax.transAxes, color=ink2, fontsize=8.5)
    ax.set_xlabel("Time (years from 2016-02-05)", color=ink)
    ax.set_ylabel("Exposure (EUR millions)", color=ink)
    ax.set_xlim(0, float(t.max()))
    ax.grid(True, color=grid, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(ink2)
    ax.tick_params(colors=ink2)
    leg = ax.legend(frameon=False, loc="upper right", fontsize=9)
    for text in leg.get_texts():
        text.set_color(ink)
    fig.tight_layout()
    path = Path(path)
    fig.savefig(path, facecolor=surface)
    plt.close(fig)
    return path


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m quantstack.risk.run_ore",
        description="Run the article's ORE exposure + XVA case in-process and write results/risk_*.",
        epilog="Canonical files: with no --samples/--market-config/--input (or with values equal to "
               "the article's: this input set, 'libor', 1000 paths) the run writes "
               "results/risk_{npv,xva,curves,cashflows,curve_pillars,exposure_*}.csv, "
               "risk_summary.json and figures/risk_exposure_profile.png. Any other run writes "
               "the same files under the prefix risk_<config>_<samples>_ (a custom --input adds "
               "its directory name: risk_<dir>_<config>_<samples>_), e.g. "
               "results/risk_xois_eur_1000_summary.json, and its ORE output goes to "
               "results/ore_output/<tag>/ (the prefix without 'risk_', e.g. xois_eur_1000) unless "
               "--out is given, so the canonical results are never overwritten.",
    )
    ap.add_argument("--input", default=str(DEFAULT_INPUT_DIR), help="directory holding ore.xml")
    ap.add_argument("--out", default=None,
                    help="ORE outputPath (gitignored; default results/ore_output, or "
                         "results/ore_output/<tag> for a non-article run)")
    ap.add_argument("--results", default=str(DEFAULT_RESULTS_DIR),
                    help="directory for the results files (default results/); non-article runs "
                         "get a risk_<config>_<samples>_ file prefix, see below")
    ap.add_argument("--samples", type=int, default=None,
                    help="override Monte Carlo paths (default: simulation.xml, 1000); "
                         "a non-article value writes tagged files")
    ap.add_argument("--market-config", default=None,
                    help="override todaysmarket configuration (default: as in ore.xml, 'libor'); "
                         "must be a <Configuration id> of todaysmarket.xml; a non-article value "
                         "writes tagged files")
    args = ap.parse_args(argv)

    if args.market_config is not None and args.market_config not in market_configurations(args.input):
        ap.error(f"--market-config {args.market_config!r} is not defined in the input's todaysmarket "
                 f"file; valid ids: {market_configurations(args.input)}")
    tag = run_tag(args.input, args.market_config, args.samples)
    out = args.out or (DEFAULT_OUTPUT_DIR if tag is None else DEFAULT_OUTPUT_DIR / tag)

    res = run_exposure(args.input, out, samples=args.samples,
                       market_configuration=args.market_config)
    written = write_results(res, args.results)
    s = res["summary"]
    cube = s["cube"] or {}
    print(f"ORE {s['ore_version']}  market config '{s['market_configuration']}'  "
          f"wall {s['wall_time_s']:.2f}s" + ("" if tag is None else f"  (non-article run: {tag})"))
    label = s["trade_id"] if "trade_id" in s else f"sum of {len(s['trade_ids'])} trades"
    print(f"NPV(Base) {label}: {s['npv_base']:,.2f} {s['npv_currency']}   "
          f"(article {ARTICLE['npv']:,.2f})")
    print(f"cube: {cube.get('ids')} trade x {cube.get('dates')} dates x {cube.get('samples')} samples")
    per_ns = s.get("by_netting_set") or {s.get("netting_set"): s}
    for ns, n in per_ns.items():
        if n.get("cva") is not None:
            pct = n.get("cva_pct_notional")
            pct_txt = "" if pct is None else f"{pct:.2f}% of notional; "
            print(f"[{ns}] CVA {n['cva']:,.2f} ({pct_txt}article {ARTICLE['cva']:,.2f})  "
                  f"DVA {n['dva']:,.2f}  FBA {n['fba']:,.2f}  FCA {n['fca']:,.2f}")
        if "max_epe" in n:
            print(f"[{ns}] EPE peak {n['max_epe']:,.0f} at t={n['max_epe_time_years']:.2f}y   "
                  f"PFE95 peak {n['max_pfe']:,.0f} at t={n['max_pfe_time_years']:.2f}y   "
                  f"ENE max {n['max_ene']:,.0f}")
    pillars = res.get("curve_pillars")
    if pillars is not None:
        print("native pricing-curve pillars: " + ", ".join(
            f"{cid} x {int((pillars['curve_id'] == cid).sum())}" for cid in dict.fromkeys(pillars["curve_id"])))
    for k, v in written.items():
        print(f"  wrote {os.path.relpath(v, Path.cwd())}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
