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
4. **Shared ``Examples/Input`` files are not identical to Example_9's.**  Running
   the swap on ``Examples/Input/{market,conventions,curveconfig,todaysmarket,
   pricingengine}`` gives NPV 1,609,885.88 (+0.05 EUR, a ``RateCutoff``/market
   data difference), and swapping in ``Examples/ORE-Python/Input/simulation.xml``
   (which adds ``Ordering=Steps``/``JoeKuoD7`` Sobol direction integers and
   CHF/JPY) moves CVA to 108,071.38 - same model, different quasi-random paths.
   Example_9's own files are the ones that reproduce the article exactly.

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
curve is column ``EUR-EONIA``.

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

TRADE_ID = "Swap_20y"
NETTING_SET = "CPTY_A"
NOTIONAL = 10_000_000.0

#: Reports pulled from ORE in memory after the run (name as in getReportNames()).
REPORTS: tuple[str, ...] = (
    "npv",
    "xva",
    f"exposure_nettingset_{NETTING_SET}",
    f"exposure_trade_{TRADE_ID}",
    "curves",
    "cashflow",
)

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
    """
    input_dir = Path(input_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
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
    reports: Iterable[str] = REPORTS,
) -> dict:
    """Run ORE in-process on ``input_dir`` and return results as DataFrames.

    Returns a dict with keys

    * ``reports``: ``{report name: DataFrame}`` for every name in ``reports`` that
      the run produced (via :func:`report_to_dataframe`);
    * ``cube``: ``{"ids", "dates", "samples", "depth"}`` of the NPV cube, read
      with ``OREApp.getCube("cube")`` (only when the simulation analytic ran);
    * ``summary``: the key numbers (see :func:`summarise`);
    * ``wall_time_s``: wall-clock seconds of ``OREApp`` construction + ``run()``;
    * ``ore_version``, ``resolved_ore_xml``, ``output_dir``, ``report_names``.

    Raises :class:`OreRunError` if ORE did not produce the ``npv`` report (or, when
    the xva analytic is active, the ``xva`` report), with the log's ALERT lines.
    """
    import ORE  # heavy import kept local so that `import quantstack.risk` stays cheap

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

    params = ORE.Parameters()
    params.fromFile(str(resolved))
    t0 = time.perf_counter()
    app = ORE.OREApp(params, False)
    app.run()
    wall = time.perf_counter() - t0

    names = set(app.getReportNames())
    required = ["npv"] + (["xva"] if "xva" in active else [])
    missing = [r for r in required if r not in names]
    if missing:
        errors = list(app.getErrors())
        app.closeLog()
        alerts = _log_alerts(output_dir)
        raise OreRunError(
            f"ORE run on {resolved} produced no {missing} report(s). "
            f"getErrors()={errors!r}. Log ALERT lines:\n" + "\n".join(alerts)
        )

    frames = {name: report_to_dataframe(app.getReport(name)) for name in reports if name in names}

    cube_info = None
    if "cube" in set(app.getCubeNames()):
        cube = app.getCube("cube")
        cube_info = {
            "ids": int(cube.numIds()),
            "dates": int(cube.numDates()),
            "samples": int(cube.samples()),
            "depth": int(cube.depth()),
        }
    version = app.version()
    app.closeLog()
    del app

    result = {
        "reports": frames,
        "cube": cube_info,
        "wall_time_s": wall,
        "ore_version": version,
        "resolved_ore_xml": str(resolved),
        "input_dir": str(Path(input_dir).resolve()),
        "output_dir": str(output_dir),
        "report_names": sorted(names),
        "market_configuration": _get_param(root.find("Markets"), "pricing"),
    }
    result["summary"] = summarise(result)
    return result


def _num(x) -> float | None:
    x = float(x)
    return None if math.isnan(x) else x


def summarise(result: Mapping) -> dict:
    """Key numbers of a :func:`run_exposure` result, JSON-serialisable."""
    frames = result["reports"]
    s: dict = {
        "ore_version": result["ore_version"],
        "wall_time_s": round(float(result["wall_time_s"]), 3),
        "market_configuration": result.get("market_configuration"),
        "trade_id": TRADE_ID,
        "netting_set": NETTING_SET,
        "cube": result.get("cube"),
    }
    npv = frames["npv"]
    row = npv.loc[npv["TradeId"] == TRADE_ID].iloc[0]
    s["npv_base"] = float(row["NPV(Base)"])
    s["npv_currency"] = str(row["BaseCurrency"])

    if "xva" in frames:
        xva = frames["xva"]
        ns = xva.loc[(xva["TradeId"] == "") & (xva["NettingSetId"] == NETTING_SET)].iloc[0]
        for col in ("CVA", "DVA", "FBA", "FCA", "BaselEPE", "BaselEEPE"):
            s[col.lower() if col.isupper() else col] = _num(ns[col])
        s["fva"] = s["fba"] + s["fca"]  # ORE sign convention: FBA >= 0 benefit, FCA <= 0 cost
        s["cva_pct_notional"] = 100.0 * s["cva"] / NOTIONAL

    exp_name = f"exposure_nettingset_{NETTING_SET}"
    if exp_name in frames:
        e = frames[exp_name]
        i_epe = int(e["EPE"].idxmax())
        i_pfe = int(e["PFE"].idxmax())
        i_ene = int(e["ENE"].idxmax())
        s.update(
            {
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
        )
    return s


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
    if summary.get("market_configuration") != "libor" or cube.get("samples") != ARTICLE["samples"]:
        out["notes"] = [
            f"Non-default run (market configuration {summary.get('market_configuration')!r}, "
            f"{cube.get('samples')} paths): differences from the article are expected; the article "
            "case is market configuration 'libor' with 1000 paths.",
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


def write_results(result: Mapping, results_dir: str | Path = DEFAULT_RESULTS_DIR) -> dict[str, str]:
    """Write ``results/risk_*.csv``, ``risk_summary.json`` and the exposure figure."""
    results_dir = Path(results_dir)
    (results_dir / "figures").mkdir(parents=True, exist_ok=True)
    frames = result["reports"]
    written: dict[str, str] = {}
    mapping = {
        f"exposure_nettingset_{NETTING_SET}": "risk_exposure_nettingset.csv",
        f"exposure_trade_{TRADE_ID}": f"risk_exposure_trade_{TRADE_ID}.csv",
        "npv": "risk_npv.csv",
        "xva": "risk_xva.csv",
        "curves": "risk_curves.csv",
        "cashflow": "risk_cashflows.csv",
    }
    for report, fname in mapping.items():
        if report in frames:
            path = results_dir / fname
            _for_csv(frames[report]).to_csv(path, index=False)  # full float precision (bridge test)
            written[report] = str(path)

    summary = dict(result["summary"])
    summary["article_comparison"] = compare_to_article(summary)
    summary["inputs"] = {
        "input_dir": os.path.relpath(result["input_dir"], REPO_ROOT),
        "source": "ORE v1.8.16.0 Examples/ORE-Python/Notebooks/Example_9/Input (+ Examples/Input "
                  "calendaradjustment.xml, currencies.xml); simulation Samples 100 -> 1000",
        "resolved_ore_xml": os.path.relpath(result["resolved_ore_xml"], REPO_ROOT),
        "curves_report_configuration": summary.get("market_configuration"),
        "curves_report_columns": "EUR = discount curve of that configuration (EUR6M under 'libor', "
                                 "EUR1D under 'xois_eur'); EUR-EURIBOR-6M = 6M projection curve; "
                                 "EUR-EONIA = OIS curve EUR1D",
    }
    summary["files"] = {k: os.path.relpath(v, REPO_ROOT) for k, v in written.items()}
    fig_path = results_dir / "figures" / "risk_exposure_profile.png"
    if f"exposure_nettingset_{NETTING_SET}" in frames:
        plot_exposure(frames[f"exposure_nettingset_{NETTING_SET}"], fig_path, summary)
        summary["files"]["figure"] = os.path.relpath(fig_path, REPO_ROOT)
        written["figure"] = str(fig_path)
    json_path = results_dir / "risk_summary.json"
    json_path.write_text(json.dumps(summary, indent=2, default=str) + "\n")
    written["summary"] = str(json_path)
    return written


def plot_exposure(exposure: pd.DataFrame, path: str | Path, summary: Mapping | None = None) -> Path:
    """EPE / ENE / PFE95 against time: the classic uncollateralised-swap profile."""
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
    ax.set_title("Exposure profile, netting set CPTY_A: 20y EUR IRS, receive 2% fixed, 10M",
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
    )
    ap.add_argument("--input", default=str(DEFAULT_INPUT_DIR), help="directory holding ore.xml")
    ap.add_argument("--out", default=str(DEFAULT_OUTPUT_DIR), help="ORE outputPath (gitignored)")
    ap.add_argument("--results", default=str(DEFAULT_RESULTS_DIR), help="where risk_*.csv/json go")
    ap.add_argument("--samples", type=int, default=None, help="override Monte Carlo paths")
    ap.add_argument("--market-config", default=None,
                    help="override todaysmarket configuration (default: as in ore.xml, 'libor')")
    args = ap.parse_args(argv)

    res = run_exposure(args.input, args.out, samples=args.samples,
                       market_configuration=args.market_config)
    written = write_results(res, args.results)
    s = res["summary"]
    cube = s["cube"] or {}
    print(f"ORE {s['ore_version']}  market config '{s['market_configuration']}'  "
          f"wall {s['wall_time_s']:.2f}s")
    print(f"NPV(Base) {TRADE_ID}: {s['npv_base']:,.2f} {s['npv_currency']}   "
          f"(article {ARTICLE['npv']:,.2f})")
    print(f"cube: {cube.get('ids')} trade x {cube.get('dates')} dates x {cube.get('samples')} samples")
    if "cva" in s:
        print(f"CVA {s['cva']:,.2f} ({s['cva_pct_notional']:.2f}% of notional; article "
              f"{ARTICLE['cva']:,.2f})  DVA {s['dva']:,.2f}  FBA {s['fba']:,.2f}  FCA {s['fca']:,.2f}")
    if "max_epe" in s:
        print(f"EPE peak {s['max_epe']:,.0f} at t={s['max_epe_time_years']:.2f}y   "
              f"PFE95 peak {s['max_pfe']:,.0f} at t={s['max_pfe_time_years']:.2f}y   "
              f"ENE max {s['max_ene']:,.0f}")
    for k, v in written.items():
        print(f"  wrote {os.path.relpath(v, Path.cwd())}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
