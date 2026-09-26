#!/usr/bin/env python
"""The whole drivetrain in ONE Python process: price, size, simulate risk,
bridge, trade, display.

    python scripts/run_all.py [--quick] [--serve] [--port 8080] [--results results] [--skip STAGE ...]

Import order: why ``import ORE`` is the first statement of this file
--------------------------------------------------------------------
``import ORE`` (open-source-risk-engine) and ``import QuantLib`` are two SWIG
wheels built against the same SWIG runtime, so they share ONE runtime type
table.  The module imported *last* owns the Python proxy classes, and QuantLib
calls made after a later ``import ORE`` can segfault (exit 139, measured on
QuantLib 1.43 / ORE 1.8.17.0).  The rule is **ORE first, QuantLib second**; see
``quantstack/_swig_order.py`` for the details and the measurements.  The pricing
and bridge modules call ``ensure_ore_before_quantlib()`` before they import
QuantLib, but a one-process driver has to be safe even if something it imports
pulls in QuantLib first, so the very first import below is ``import ORE``, and
``ensure_ore_before_quantlib()`` is then asserted before anything else.  Do not
move another import above it (``tests/test_run_all.py`` checks this).

Stages (each logs one timing line; all go into ``<results>/run_all_summary.json``)
--------------------------------------------------------------------------------
0. imports     all five libraries in this one process, versions printed: the
               article's "they all import into one process", made checkable.
1. pricing     QuantLib: one European call, four engines
               (``quantstack.pricing.four_engines.main``).
2. allocation  skfolio: max-Sharpe vs HRP (``quantstack.allocation.compare.main``).
3. risk        ORE: 20y EUR swap NPV + exposure simulation + XVA
               (``run_exposure`` + ``summarise`` + ``write_results``), 1000 paths
               (``--quick``: 16 paths, written under the tagged prefix
               ``risk_libor_16_``, never over the canonical ``risk_*`` files).
4. bridge      ORE curve -> standalone QuantLib re-price.  Always reads the
               canonical committed ``results/risk_curves.csv`` / ``risk_npv.csv``
               (so its numbers are the same in ``--quick`` mode), and checks that
               the NPV and curves report of *this* process's ORE run match them.
5. execution   NautilusTrader backtest with skfolio HRP inside the event loop,
               wired LIVE to the display: a ``PerspectiveSink`` is served by a
               ``BackgroundDashboard`` *before* the backtest starts and is passed
               as the backtest's sink, so every daily equity point, positions
               snapshot and fill streams into the Perspective tables while the
               engine runs.  The backtest CLI's own code writes the
               ``execution_*`` files.  The three table sizes are then read back
               over a real websocket client, and the equity curve read back out of
               the Perspective table is checked against the sink's curve
               (bit-exact) and the engine's ``execution_equity.csv`` (to the cent).
6. positions   the positions -> risk wire: ``execution_positions.csv`` ->
               ``ore_output/portfolio_equity.xml`` (gitignored) via
               ``portfolio_writer.positions_csv_to_ore_portfolio``; ORE must parse
               one EquityPosition trade per position.
7. dashboard   ``dashboard_summary.json`` exactly as
               ``python -m quantstack.dashboard.server --once`` writes it (its
               ``main()`` called in-process: replay + websocket self-test).

Options
-------
``--quick``    ORE with 16 samples (tagged outputs) and a short backtest (AAPL,
               MSFT, JPM over 2018, lookback 60, no order-sequencing experiment):
               ~10 s on 4 shared CPUs (a full run takes ~27 s), for CI.  A quick
               run never writes over the committed files: when ``--results`` is
               the repository's ``results/`` (the default), its outputs go to
               ``results/quick/`` (gitignored) instead.
``--serve``    after the last stage keep the dashboard up on
               ``127.0.0.1:--port`` (default 8080) until Ctrl-C.  It is started
               on that port before the backtest, so you can watch the run live.
               Without ``--serve`` the dashboard lives only while the backtest
               runs (on an OS-assigned port unless ``--port`` is given) and is
               stopped cleanly afterwards.
``--results``  output directory (default: the repository's ``results/``).  The
               default full run regenerates every canonical results file; only
               timing fields change (``--serve`` also records its own argv,
               ``serve: true`` and port in ``run_all_summary.json``).
``--skip``     skip stages by name (debugging): pricing allocation risk bridge
               execution positions dashboard.  Later stages then use whatever
               files are already in the results directory.

Exit status: 0 all stages passed; 1 a stage failed (the summary JSON is still
written, with ``status: "failed"`` and the stage's error); 2 bad arguments;
130 interrupted.

Security: the dashboard has no authentication (see
``quantstack/dashboard/server.py``); this script only ever binds 127.0.0.1.
"""

import ORE  # noqa: I001  MUST stay the first import (SWIG type table): see the docstring

import argparse
import asyncio
import contextlib
import json
import platform
import signal
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # runnable without `pip install -e .`
    sys.path.insert(0, str(REPO_ROOT))

from quantstack._swig_order import ensure_ore_before_quantlib  # noqa: E402

if not ensure_ore_before_quantlib():  # cannot fail after the import above; kept as the explicit guard
    raise SystemExit("QuantLib was imported before ORE; see quantstack/_swig_order.py")

CANONICAL_RESULTS = REPO_ROOT / "results"
QUICK_SUBDIR = "quick"
SUMMARY_NAME = "run_all_summary.json"
HOST = "127.0.0.1"
DEFAULT_SERVE_PORT = 8080

QUICK_ORE_SAMPLES = 16
QUICK_BACKTEST = {"symbols": ("AAPL", "MSFT", "JPM"), "start": "2018-01-01", "end": "2018-12-31",
                  "lookback": 60}

STAGES = ("imports", "pricing", "allocation", "risk", "bridge", "execution", "positions", "dashboard")
SKIPPABLE = STAGES[1:]


class StageError(RuntimeError):
    """A stage ran but its result failed a check."""


def log(msg: str) -> None:
    print(f"[run_all] {msg}", flush=True)


def _rel(path: Path | str | None) -> str | None:
    if path is None:
        return None
    p = Path(path).resolve()
    try:
        return p.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(p)


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise StageError(msg)


@contextlib.contextmanager
def _module_results_dir(module, results_dir: Path, figures_attr: str = "FIGURES_DIR"):
    """Point a module whose outputs go to its ``RESULTS_DIR``/``FIGURES_DIR``
    globals at ``results_dir`` for the duration (the tests do the same)."""
    old = {"RESULTS_DIR": module.RESULTS_DIR, figures_attr: getattr(module, figures_attr)}
    if Path(module.RESULTS_DIR).resolve() == results_dir.resolve():
        yield
        return
    module.RESULTS_DIR = results_dir
    setattr(module, figures_attr, results_dir / "figures")
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(module, k, v)


@dataclass
class Context:
    results_dir: Path
    canonical: bool  # results_dir is the repository's results/
    quick: bool
    serve: bool
    port: int  # 0 = OS-assigned
    risk_result: dict | None = None
    sink: Any = None
    dashboard: Any = None
    websocket_tables: dict | None = None
    versions: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# stage 0: five libraries, one process
# --------------------------------------------------------------------------


def stage_imports(ctx: Context) -> dict:
    import QuantLib
    import skfolio
    import nautilus_trader
    import perspective

    import matplotlib
    import numpy
    import pandas
    import pyarrow
    import scipy
    import sklearn
    import tornado

    order = list(sys.modules)
    ore_first = order.index("ORE") < order.index("QuantLib")
    _check(ore_first, "QuantLib was loaded before ORE (see quantstack/_swig_order.py)")
    ctx.versions = {
        "python": platform.python_version(),
        "perspective": perspective.__version__,
        "QuantLib": QuantLib.__version__,
        "ORE": ORE.__version__,
        "skfolio": skfolio.__version__,
        "nautilus_trader": nautilus_trader.__version__,
        "pandas": pandas.__version__,
        "numpy": numpy.__version__,
        "pyarrow": pyarrow.__version__,
        "scipy": scipy.__version__,
        "scikit-learn": sklearn.__version__,
        "matplotlib": matplotlib.__version__,
        "tornado": tornado.version,
    }
    v = ctx.versions
    log(f"all five import into one process: perspective {v['perspective']} | QuantLib {v['QuantLib']} | "
        f"ORE {v['ORE']} | skfolio {v['skfolio']} | nautilus_trader {v['nautilus_trader']} "
        f"(Python {v['python']}; ORE loaded before QuantLib: {ore_first})")
    return {"five_libraries": {k: v[k] for k in ("perspective", "QuantLib", "ORE", "skfolio",
                                                 "nautilus_trader")},
            "ore_loaded_before_quantlib": ore_first}


# --------------------------------------------------------------------------
# stage 1: pricing
# --------------------------------------------------------------------------


def stage_pricing(ctx: Context) -> dict:
    from quantstack.pricing import four_engines as fe

    with _module_results_dir(fe, ctx.results_dir):
        s = fe.main()
    engines = {name: {"finest_level": e["finest_level"], "finest_price": e["finest_price"],
                      "abs_error_vs_analytic": e["abs_error_vs_analytic"], "check_passed": e["check_passed"]}
               for name, e in s["engines"].items()}
    _check(all(e["check_passed"] for e in engines.values()), f"a finest-level check failed: {engines}")
    _check(s["instrument_identity"]["passed"], "more than one VanillaOption was priced")
    repro = s["article_setup_repro"]
    return {
        "analytic_price": s["analytic_price"],
        "year_fraction": s["market"]["year_fraction"],
        "engines": engines,
        "one_instrument_for_all_rows": s["instrument_identity"]["passed"],
        "article_repro_366_day_life": {
            "evaluation_date": repro["evaluation_date"],
            "prices": {k: v["price"] for k, v in repro["prices"].items()},
            "matches_article_4dp": repro["matches_article_4dp"],
        },
    }


# --------------------------------------------------------------------------
# stage 2: allocation
# --------------------------------------------------------------------------


def stage_allocation(ctx: Context) -> dict:
    from quantstack.allocation import compare

    with _module_results_dir(compare, ctx.results_dir):
        s = compare.main()
    ms, hrp = s["in_sample"]["max_sharpe"], s["in_sample"]["hrp"]
    oos = s["out_of_sample"]
    art = s["article_comparison"]
    return {
        "skfolio_version": s["skfolio_version"],
        "max_sharpe": {"n_near_zero": ms["n_near_zero"], "n_assets": ms["n_assets"],
                       "max_weight": ms["max_weight"], "effective_n": ms["effective_n"],
                       "oos_sharpe": oos["max_sharpe"]["annualized_sharpe"]},
        "hrp": {"n_near_zero": hrp["n_near_zero"], "n_assets": hrp["n_assets"],
                "max_weight": hrp["max_weight"], "effective_n": hrp["effective_n"],
                "oos_sharpe": oos["hrp"]["annualized_sharpe"]},
        "all_match_article_at_printed_precision": art["all_match_at_printed_precision"],
        "qualitative_story_holds": art["qualitative_story_holds"],
    }


# --------------------------------------------------------------------------
# stage 3: risk (ORE)
# --------------------------------------------------------------------------


def stage_risk(ctx: Context) -> dict:
    from quantstack.risk import run_ore

    samples = QUICK_ORE_SAMPLES if ctx.quick else None
    tag = run_ore.run_tag(run_ore.DEFAULT_INPUT_DIR, None, samples)
    ore_out = ctx.results_dir / "ore_output"
    if tag is not None:
        ore_out = ore_out / tag  # same layout as `python -m quantstack.risk.run_ore --samples N`
    res = run_ore.run_exposure(run_ore.DEFAULT_INPUT_DIR, ore_out, samples=samples)
    s = run_ore.summarise(res)
    written = run_ore.write_results(res, ctx.results_dir)
    ctx.risk_result = res
    cube = s.get("cube") or {}
    expected_samples = samples or run_ore.ARTICLE["samples"]
    _check(cube.get("samples") == expected_samples,
           f"ORE cube has {cube.get('samples')} samples, expected {expected_samples}")
    return {
        "canonical": tag is None,
        "file_prefix": run_ore.results_prefix(res),
        "ore_version": s["ore_version"],
        "market_configuration": s["market_configuration"],
        "npv_base": s["npv_base"],
        "cva": s.get("cva"),
        "cva_pct_notional": s.get("cva_pct_notional"),
        "dva": s.get("dva"),
        "max_epe": s.get("max_epe"),
        "max_epe_time_years": s.get("max_epe_time_years"),
        "max_pfe": s.get("max_pfe"),
        "max_pfe_time_years": s.get("max_pfe_time_years"),
        "cube": cube,
        "ore_wall_time_s": s["wall_time_s"],
        "ore_output_dir": _rel(ore_out),
        "files": {k: _rel(v) for k, v in written.items()},
    }


# --------------------------------------------------------------------------
# stage 4: bridge
# --------------------------------------------------------------------------


def _live_vs_committed(risk_result: dict, curves_csv: Path, npv_csv: Path) -> dict:
    """Does this process's ORE run agree with the committed files the bridge reads?

    The NPV and the ``curves`` report come from the pricing market, not the
    simulation, so they do not depend on the path count: in ``--quick`` mode
    (16 paths) they must still equal the committed 1000-path run's files.
    """
    import numpy as np
    import pandas as pd

    from quantstack.risk import run_ore

    live_npv = float(run_ore.summarise(risk_result)["npv_base"])
    committed_npv = float(pd.read_csv(npv_csv)["NPV(Base)"].iloc[0])
    live_curves = risk_result["reports"].get("curves")
    committed = pd.read_csv(curves_csv)
    max_df_diff = None
    if live_curves is not None:
        num = [c for c in committed.columns if c not in ("Tenor", "Date")]
        a = live_curves[num].to_numpy(dtype=float)
        b = committed[num].to_numpy(dtype=float)
        if a.shape == b.shape:
            max_df_diff = float(np.nanmax(np.abs(a - b)))
    return {
        "live_ore_npv": live_npv,
        "committed_ore_npv": committed_npv,
        "npv_abs_diff_eur": abs(live_npv - committed_npv),
        "curves_max_abs_discount_factor_diff": max_df_diff,
    }


def stage_bridge(ctx: Context) -> dict:
    from quantstack.risk import bridge_test

    curves_csv = CANONICAL_RESULTS / "risk_curves.csv"
    npv_csv = CANONICAL_RESULTS / "risk_npv.csv"
    log(f"bridge: reading the canonical committed curves {_rel(curves_csv)} and {_rel(npv_csv)} "
        "(not this run's ORE output), so the bridge numbers are the same in --quick mode")
    for p in (curves_csv, npv_csv):
        _check(p.exists(), f"{_rel(p)} not found (committed; regenerate with a full run)")
    s = bridge_test.run_bridge_test(curves_csv, npv_csv, results_dir=ctx.results_dir)
    live = None
    if ctx.risk_result is not None:
        live = _live_vs_committed(ctx.risk_result, curves_csv, npv_csv)
        _check(live["npv_abs_diff_eur"] < 0.005,
               f"this run's ORE NPV {live['live_ore_npv']:,.2f} differs from the committed "
               f"{live['committed_ore_npv']:,.2f} the bridge reads")
        _check(live["curves_max_abs_discount_factor_diff"] is not None
               and live["curves_max_abs_discount_factor_diff"] < 1e-12,
               f"this run's ORE curves report differs from {_rel(curves_csv)}: {live}")
    a = s["gap_attribution"]
    return {
        "curves_input": _rel(curves_csv),
        "ore_npv": s["ore_npv"],
        "ql_npv": s["ql_npv"],
        "diff_eur": s["diff_eur"],
        "diff_bp": s["diff_bp"],
        "schedules_match_ore_cashflow_report": s["schedule_match"].get("all_match"),
        "extrapolation_beyond_grid_end_eur": a.get("extrapolation_beyond_grid_end_eur"),
        "interpolation_within_grid_eur": a.get("interpolation_within_grid_eur"),
        "extrapolation_share_pct": a.get("extrapolation_share_pct"),
        "this_run_ore_matches_bridge_input": live,
    }


# --------------------------------------------------------------------------
# stage 5: execution, streamed live into Perspective
# --------------------------------------------------------------------------


def _start_dashboard(ctx: Context, sink) -> Any:
    from quantstack.dashboard.server import BackgroundDashboard

    try:
        dash = BackgroundDashboard(sink, host=HOST, port=ctx.port).start()
    except OSError as exc:
        raise StageError(f"cannot bind the dashboard to {HOST}:{ctx.port} ({exc}); pick another --port") from exc
    ctx.dashboard = dash
    return dash


def _read_tables_over_websocket(ws_url: str, timeout: float = 60.0) -> dict:
    """A real websocket client (tornado + perspective.AsyncClient) reads every
    data table back, via the dashboard's own client helper."""
    from quantstack.dashboard import server as ds

    return asyncio.run(asyncio.wait_for(ds._read_tables(ws_url, ds.TABLE_NAMES), timeout))


def _backtest_argv(ctx: Context) -> list[str]:
    argv = ["--results-dir", str(ctx.results_dir)]
    if ctx.quick:
        q = QUICK_BACKTEST
        argv += ["--symbols", ",".join(q["symbols"]), "--start", q["start"], "--end", q["end"],
                 "--lookback", str(q["lookback"]), "--no-sequencing-experiment"]
    return argv


def stage_execution(ctx: Context) -> dict:
    from quantstack.contracts import RecordingSink, read_equity_csv
    from quantstack.dashboard.server import PerspectiveSink
    from quantstack.execution import backtest

    sink = PerspectiveSink()
    sink.set_meta(data_source="live", note="live: NautilusTrader backtest streaming from scripts/run_all.py")
    ctx.sink = sink
    dash = _start_dashboard(ctx, sink)
    log(f"dashboard live at {dash.url} while the backtest runs (Perspective tables fed by the engine)")
    recorder = RecordingSink()
    stream = backtest.TeeSink(sink, recorder)  # recorder = the sink-side copy of what was streamed
    try:
        summary = backtest.main(_backtest_argv(ctx), sink=stream)
        alloc = "hrp"  # the backtest CLI's default allocator; _backtest_argv never changes it
        main = summary[alloc]
        local_sizes = sink.table_sizes()
        tables = _read_tables_over_websocket(dash.ws_url)
    finally:
        if not ctx.serve:
            dash.stop()
            ctx.dashboard = None
            log("dashboard stopped (use --serve to keep it up)")
    ws_sizes = {name: len(tables[name]) for name in ("positions", "equity", "fills")}
    ctx.websocket_tables = ws_sizes
    n_symbols = len(summary["universe"])
    _check(ws_sizes == local_sizes, f"websocket read {ws_sizes} but the sink holds {local_sizes}")
    _check(ws_sizes["fills"] == summary["fills"] > 0,
           f"fills table has {ws_sizes['fills']} rows, the engine made {summary['fills']} fills")
    _check(ws_sizes["positions"] == n_symbols,
           f"positions table has {ws_sizes['positions']} rows for {n_symbols} symbols")
    _check(ws_sizes["equity"] == main["stats"]["days_published"] > 0,
           f"equity table has {ws_sizes['equity']} rows, the strategy published "
           f"{main['stats']['days_published']} days")

    # The equity curve read back OUT of Perspective (over the websocket) ...
    ws_curve = {r["date"]: r["equity"] for r in tables["equity"]}
    # ... is bit-for-bit what the strategy streamed into the sink ...
    _check(ws_curve == recorder.equity,
           "equity read back from Perspective differs from the curve the engine streamed")
    # ... and, to the cent, the engine's curve in execution_equity.csv.
    eq_csv = ctx.results_dir / "execution_equity.csv"
    engine_curve = read_equity_csv(eq_csv, f"equity_{alloc}")
    engine = {ts.strftime("%Y-%m-%d"): float(v) for ts, v in engine_curve.items()}
    _check(set(engine) == set(ws_curve), "Perspective equity dates differ from execution_equity.csv")
    max_diff = max(abs(ws_curve[d] - engine[d]) for d in engine)
    _check(max_diff <= 0.005 + 1e-6, f"Perspective curve differs from the engine's by {max_diff:.6f} USD")
    last = max(ws_curve)
    _check(ws_curve[last] == main["metrics"]["final_equity"],
           "last Perspective equity point differs from the engine's final equity")
    sink.set_meta(data_source="live",
                  note=f"live run finished: {summary['fills']} fills, final equity {ws_curve[last]:,.2f}")
    log(f"websocket read-back: positions {ws_sizes['positions']}, equity {ws_sizes['equity']}, "
        f"fills {ws_sizes['fills']} rows; equity curve out of Perspective == streamed curve (bit-exact), "
        f"== execution_equity.csv to {max_diff:.4f} USD")
    m = main["metrics"]
    return {
        "universe": summary["universe"],
        "window": summary["window"],
        "fills": summary["fills"],
        "rejections": summary["rejections"],
        "denied": summary["denied"],
        "first_fill_date": summary["first_fill_date"],
        alloc: {"final_equity": m["final_equity"], "cagr": m["cagr"], "max_drawdown": m["max_drawdown"],
                "sharpe": m["sharpe"]},
        "equal_engine_final_equity": summary["equal_engine"]["metrics"]["final_equity"],
        "equal_pandas_final_equity": summary["equal_pandas"]["metrics"]["final_equity"],
        "qualitative_story_holds": summary["comparison"]["qualitative_story_holds"],
        "dashboard": {
            "streamed_live": True,
            "port": dash.port if ctx.serve else "ephemeral",
            "table_sizes_over_websocket": ws_sizes,
            "hosted_tables": tables["hosted_tables"],
            "equity_readback": {
                "points": len(ws_curve),
                "first": [min(ws_curve), ws_curve[min(ws_curve)]],
                "last": [last, ws_curve[last]],
                "bit_exact_vs_streamed_curve": True,
                "max_abs_diff_vs_execution_equity_csv_usd": max_diff,
                "last_equals_engine_final_equity": True,
            },
        },
        "files": {k: v for k, v in summary["outputs"].items()},
    }


# --------------------------------------------------------------------------
# stage 6: positions -> risk wire
# --------------------------------------------------------------------------


def stage_positions(ctx: Context) -> dict:
    from quantstack.contracts import read_positions_csv
    from quantstack.risk import portfolio_writer

    csv_path = ctx.results_dir / "execution_positions.csv"
    _check(csv_path.exists(), f"{_rel(csv_path)} not found: run the execution stage first")
    xml_path = ctx.results_dir / "ore_output" / "portfolio_equity.xml"
    portfolio_writer.positions_csv_to_ore_portfolio(csv_path, xml_path)
    snap = read_positions_csv(csv_path)
    trades = portfolio_writer.parse_with_ore(path=xml_path)
    types = sorted({t for _, t in trades})
    _check(len(trades) == len(snap.positions),
           f"ORE parsed {len(trades)} trades from {len(snap.positions)} positions")
    _check(types == ["EquityPosition"], f"unexpected ORE trade types {types}")
    log(f"positions -> risk: {len(snap.positions)} positions -> {_rel(xml_path)} -> ORE parsed "
        f"{len(trades)} EquityPosition trades")
    return {
        "positions_csv": _rel(csv_path),
        "ore_portfolio_xml": _rel(xml_path),
        "as_of": snap.as_of.isoformat(),
        "n_positions": len(snap.positions),
        "n_trades_parsed_by_ore": len(trades),
        "trade_types": types,
        "trade_ids": [tid for tid, _ in trades],
        "cash_not_a_trade": snap.cash,
    }


# --------------------------------------------------------------------------
# stage 7: dashboard summary
# --------------------------------------------------------------------------


def stage_dashboard(ctx: Context) -> dict:
    from quantstack.dashboard import server as ds

    if ctx.canonical:
        argv = ["--once"]  # exactly `python -m quantstack.dashboard.server --once`
        out = ds.RESULTS_DIR / ds.SUMMARY_NAME
    else:
        out = ctx.results_dir / ds.SUMMARY_NAME
        argv = ["--once", "--replay", str(ctx.results_dir / "execution_equity.csv"),
                str(ctx.results_dir / "execution_positions.csv"), "--summary", str(out)]
    code = ds.main(argv)
    _check(code == 0, f"dashboard main returned {code}")
    s = json.loads(out.read_text())
    replay, wire = s["replay"], s["wire_selftest"]
    _check(not replay["is_demo"], f"dashboard fell back to demo data: {replay['fallback_reason']}")
    _check(bool(wire.get("origin_policy_enforced")) and bool(wire.get("float_round_trip_bit_exact"))
           and bool(wire.get("indexed_update_overwrote_in_place")),
           f"dashboard websocket self-test failed: {wire}")
    return {
        "summary_file": _rel(out),
        "summary_kind": s.get("summary_kind"),
        "replayed_table_sizes": replay["table_sizes_after_load"],
        "equity_source_column": replay["equity_source_column"],
        "selftest_origin_policy_enforced": wire["origin_policy_enforced"],
        "selftest_float_round_trip_bit_exact": wire["float_round_trip_bit_exact"],
        "selftest_indexed_update_overwrote_in_place": wire["indexed_update_overwrote_in_place"],
        "npm_pins_match_perspective_python":
            s["npm_packages_used_by_static_index_html"]["all_pinned_to_perspective_python"],
    }


# stage name -> function(ctx) -> key numbers.  Deliberately unannotated: a module-level
# typing.Callable[[Context], dict] is kept in typing's cache until interpreter exit, which
# pins this module (and its ORE reference) and makes SWIG print spurious "memory leak"
# lines for QuantLib globals at shutdown when the script is imported (tests).
STAGE_FUNCS = {
    "imports": stage_imports,
    "pricing": stage_pricing,
    "allocation": stage_allocation,
    "risk": stage_risk,
    "bridge": stage_bridge,
    "execution": stage_execution,
    "positions": stage_positions,
    "dashboard": stage_dashboard,
}


def _headline(name: str, n: dict) -> str:
    """The key numbers of a stage, for its one-line log."""
    try:
        if name == "imports":
            return ", ".join(f"{k} {v}" for k, v in n["five_libraries"].items())
        if name == "pricing":
            e = n["engines"]
            return (f"analytic {n['analytic_price']:.6f}; CRR {e['binomial_crr']['finest_price']:.6f}, "
                    f"FD {e['fd_black_scholes']['finest_price']:.6f}, MC {e['mc_pseudo_random']['finest_price']:.6f}; "
                    f"366-day repro {n['article_repro_366_day_life']['prices']['analytic']:.4f}")
        if name == "allocation":
            ms, h = n["max_sharpe"], n["hrp"]
            return (f"max-Sharpe {ms['n_near_zero']}/{ms['n_assets']} zeroed, max {ms['max_weight']:.1%}, "
                    f"eff N {ms['effective_n']:.2f}; HRP eff N {h['effective_n']:.2f}; "
                    f"OOS Sharpe {ms['oos_sharpe']:.3f} vs {h['oos_sharpe']:.3f}")
        if name == "risk":
            c = n["cube"]
            return (f"NPV {n['npv_base']:,.2f}, CVA {n['cva']:,.2f}, EPE peak {n['max_epe']:,.0f} at "
                    f"{n['max_epe_time_years']:.1f}y, PFE95 {n['max_pfe']:,.0f} at {n['max_pfe_time_years']:.1f}y, "
                    f"cube {c.get('ids')}x{c.get('dates')}x{c.get('samples')}"
                    + ("" if n["canonical"] else f" (non-canonical, prefix {n['file_prefix']})"))
        if name == "bridge":
            return (f"ORE {n['ore_npv']:,.2f} vs QuantLib {n['ql_npv']:,.2f} = {n['diff_eur']:,.2f} EUR "
                    f"= {n['diff_bp']:.4f} bp; extrapolation {n['extrapolation_share_pct']:.1f}%")
        if name == "execution":
            alloc = "hrp" if "hrp" in n else "equal"
            return (f"{n['fills']} fills, {n['rejections']} rejected, first fill {n['first_fill_date']}, "
                    f"{alloc} 1M -> {n[alloc]['final_equity']:,.2f}; tables over websocket "
                    f"{n['dashboard']['table_sizes_over_websocket']}")
        if name == "positions":
            return f"{n['n_positions']} positions -> {n['n_trades_parsed_by_ore']} ORE trades"
        if name == "dashboard":
            return f"{n['summary_file']} ({n['summary_kind']}), tables {n['replayed_table_sizes']}"
    except (KeyError, TypeError, ValueError):
        pass
    return ""


def _write_summary(ctx: Context, record: dict) -> Path:
    path = ctx.results_dir / SUMMARY_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, default=str) + "\n")
    return path


def _serve_forever(ctx: Context) -> None:
    from quantstack.dashboard import server as ds

    if ctx.dashboard is None:  # execution skipped or failed early: serve what is on disk
        data = ds.load_replay(ctx.results_dir / "execution_equity.csv",
                              ctx.results_dir / "execution_positions.csv",
                              ctx.results_dir / "execution_fills.csv")
        sink = ds.PerspectiveSink()
        ds.populate_sink(sink, data)
        _start_dashboard(ctx, sink)
    log(f"serving the dashboard at {ctx.dashboard.url} (no auth, loopback only); Ctrl-C to stop")

    def _terminate(signum, frame):  # SIGTERM (kill, docker stop) stops it as cleanly as Ctrl-C
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _terminate)
    try:
        while ctx.dashboard.running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print()
    finally:
        ctx.dashboard.stop()
        log("dashboard stopped")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="python scripts/run_all.py",
        description="The whole drivetrain in one Python process: QuantLib pricing, skfolio allocation, "
                    "ORE exposure + XVA, the ORE -> QuantLib bridge, a NautilusTrader backtest streamed "
                    "live into Perspective, the positions -> ORE wire and the dashboard summary.",
        epilog=f"Stages: {' '.join(STAGES)}. Writes <results>/{SUMMARY_NAME}. See the module docstring.",
    )
    ap.add_argument("--quick", action="store_true",
                    help=f"ORE with {QUICK_ORE_SAMPLES} samples (tagged outputs) and a short backtest "
                         f"({', '.join(QUICK_BACKTEST['symbols'])}, 2018, lookback {QUICK_BACKTEST['lookback']}); "
                         "with the default --results its outputs go to results/quick/")
    ap.add_argument("--serve", action="store_true",
                    help="after the last stage keep the dashboard up on 127.0.0.1:--port until Ctrl-C")
    ap.add_argument("--port", type=int, default=None,
                    help=f"dashboard port (default {DEFAULT_SERVE_PORT} with --serve; otherwise an "
                         "OS-assigned free port, used only while the backtest runs)")
    ap.add_argument("--results", default=None,
                    help="results directory (default: the repository's results/)")
    ap.add_argument("--skip", nargs="+", action="extend", default=[], choices=SKIPPABLE,
                    metavar="STAGE", help=f"skip stage(s): {' '.join(SKIPPABLE)}")
    args = ap.parse_args(argv)
    if args.port is not None and not 0 <= args.port <= 65535:
        ap.error(f"--port {args.port} is not a valid port")
    return args


def resolve_results_dir(results: str | None, quick: bool) -> tuple[Path, bool, bool]:
    """``(directory, is the canonical results/, redirected)`` for ``--results``/``--quick``.

    A quick run aimed at the repository's ``results/`` (the default) is
    redirected to ``results/quick/`` so it never overwrites committed files.
    """
    results_dir = Path(results).resolve() if results else CANONICAL_RESULTS.resolve()
    canonical = results_dir == CANONICAL_RESULTS.resolve()
    if quick and canonical:
        return CANONICAL_RESULTS.resolve() / QUICK_SUBDIR, False, True
    return results_dir, canonical, False


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    results_dir, canonical, redirected = resolve_results_dir(args.results, args.quick)
    results_dir.mkdir(parents=True, exist_ok=True)
    port = args.port if args.port is not None else (DEFAULT_SERVE_PORT if args.serve else 0)
    ctx = Context(results_dir=results_dir, canonical=canonical, quick=args.quick, serve=args.serve, port=port)
    skip = set(args.skip)

    mode = "QUICK (non-canonical)" if args.quick else "FULL (canonical)" if canonical else "FULL"
    log(f"{mode} run -> {_rel(results_dir)}" + (f"; skipping {' '.join(n for n in STAGES if n in skip)}" if skip else ""))
    if redirected:
        log("--quick never writes over the committed results: outputs go to results/quick/ (gitignored)")

    record: dict = {
        "script": "scripts/run_all.py",
        "argv": list(sys.argv[1:] if argv is None else argv),
        "quick": args.quick,
        "serve": args.serve,
        "results_dir": _rel(results_dir),
        "canonical_results_dir": canonical,
        "status": "running",
        "failed_stage": None,
        "error": None,
        "versions": {},
        "stage_seconds": {},
        "stages": {},
        "dashboard_tables_over_websocket": None,
        "total_seconds": None,
    }
    t_all = time.perf_counter()
    exit_code = 0
    try:
        for i, name in enumerate(STAGES):
            label = f"{i}/{len(STAGES) - 1} {name:<10}"
            if name in skip:
                record["stages"][name] = {"status": "skipped"}
                record["stage_seconds"][name] = None
                log(f"{label} skipped")
                continue
            t0 = time.perf_counter()
            try:
                numbers = STAGE_FUNCS[name](ctx)
            except (Exception, SystemExit) as exc:  # noqa: BLE001 -- report any stage failure, then stop
                dt = time.perf_counter() - t0
                if isinstance(exc, SystemExit):
                    msg = f"stage exited with status {exc.code}"
                else:
                    msg = f"{type(exc).__name__}: {exc}"
                    traceback.print_exc()
                record["stages"][name] = {"status": "failed", "seconds": round(dt, 3), "error": msg}
                record["stage_seconds"][name] = round(dt, 3)
                record.update(status="failed", failed_stage=name, error=msg)
                log(f"{label} FAILED after {dt:.1f} s: {msg}")
                exit_code = 1
                break
            dt = time.perf_counter() - t0
            record["stages"][name] = {"status": "ok", "seconds": round(dt, 3), "numbers": numbers}
            record["stage_seconds"][name] = round(dt, 3)
            record["versions"] = ctx.versions
            record["dashboard_tables_over_websocket"] = ctx.websocket_tables
            log(f"{label} ok {dt:7.1f} s  {_headline(name, numbers)}")
    except KeyboardInterrupt:
        record.update(status="interrupted", error="KeyboardInterrupt")
        exit_code = 130
    finally:
        if record["status"] == "running":
            record["status"] = "ok"
        record["total_seconds"] = round(time.perf_counter() - t_all, 3)
        path = _write_summary(ctx, record)
        if exit_code != 0 and ctx.dashboard is not None:
            ctx.dashboard.stop()
            ctx.dashboard = None

    if exit_code == 0:
        timings = ", ".join(f"{k} {v:.1f}s" for k, v in record["stage_seconds"].items() if v is not None)
        log(f"all stages passed in {record['total_seconds']:.1f} s ({timings}); wrote {_rel(path)}")
        if args.serve:
            _serve_forever(ctx)
    elif exit_code == 1:
        log(f"FAILED at stage '{record['failed_stage']}': {record['error']} (summary: {_rel(path)})")
    else:
        log(f"interrupted (summary: {_rel(path)})")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
