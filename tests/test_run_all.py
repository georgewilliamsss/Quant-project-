"""Tests for scripts/run_all.py, the one-process driver.

Fast tests check the import-order guard (statically and in a fresh
interpreter), the results-directory rules, the summary on success, skip and
failure, and the ``sink=`` hook the driver needs from the backtest CLI.  The
slow test runs ``scripts/run_all.py --quick`` end to end in a subprocess.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "run_all.py"


@pytest.fixture(scope="module")
def run_all():
    """The script loaded as a module (it is not a package member), once per session."""
    name = "quantstack_run_all_script"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, SCRIPT)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


# --------------------------------------------------------------------------
# import order
# --------------------------------------------------------------------------


def test_first_statement_after_the_docstring_is_the_ore_import_guard():
    tree = ast.parse(SCRIPT.read_text())
    assert ast.get_docstring(tree), "the module docstring explains the import order"
    assert "_swig_order.py" in ast.get_docstring(tree)
    first = tree.body[1]  # body[0] is the docstring
    is_ore = isinstance(first, ast.Import) and [a.name for a in first.names] == ["ORE"]
    is_guard = isinstance(first, ast.ImportFrom) and first.module == "quantstack._swig_order"
    assert is_ore or is_guard, f"first statement is {ast.dump(first)}"
    # and nothing at module level imports QuantLib (the stages import it lazily)
    top_level = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name for n in top_level for a in n.names} | {
        n.module for n in top_level if isinstance(n, ast.ImportFrom)}
    assert "QuantLib" not in names


def test_ore_is_the_first_third_party_module_the_script_loads(tmp_path):
    """In a fresh interpreter: loading the script pulls in ORE before any other
    non-stdlib module, and after stage 0 imported all five libraries ORE is
    still ahead of QuantLib in import order."""
    code = textwrap.dedent(f"""
        import importlib.util, json, sys
        from pathlib import Path
        before = set(sys.modules)
        spec = importlib.util.spec_from_file_location("run_all", {str(SCRIPT)!r})
        m = importlib.util.module_from_spec(spec)
        sys.modules["run_all"] = m
        spec.loader.exec_module(m)
        new = [n for n in sys.modules if n not in before and n != "run_all"]
        third_party = [n for n in new if n.split(".")[0] not in sys.stdlib_module_names
                       and not n.startswith("_")]
        ql_loaded_at_import = "QuantLib" in sys.modules
        ctx = m.Context(results_dir=Path({str(tmp_path)!r}), canonical=False, quick=True,
                        serve=False, port=0)
        numbers = m.stage_imports(ctx)
        order = list(sys.modules)
        print("@@" + json.dumps({{"third_party": third_party, "ql_at_import": ql_loaded_at_import,
                                 "ore": order.index("ORE"), "ql": order.index("QuantLib"),
                                 "numbers": numbers}}))
    """)
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          cwd=tmp_path, env=env, timeout=300)
    assert proc.returncode == 0, proc.stderr[-3000:]
    line = next(ln for ln in proc.stdout.splitlines() if ln.startswith("@@"))
    out = json.loads(line[2:])
    # Everything non-stdlib loaded before the script's second import (quantstack) came
    # from `import ORE`: ORE itself and the SWIG runtime type table it registers.
    tp = out["third_party"]
    before_quantstack = tp[: tp.index("quantstack")]
    assert "ORE" in before_quantstack and set(before_quantstack) <= {"ORE", "swig_runtime_data5"}, tp[:5]
    assert out["ql_at_import"] is False
    assert out["ore"] < out["ql"]
    assert out["numbers"]["ore_loaded_before_quantlib"] is True
    assert set(out["numbers"]["five_libraries"]) == {"perspective", "QuantLib", "ORE", "skfolio",
                                                     "nautilus_trader"}


# --------------------------------------------------------------------------
# CLI rules
# --------------------------------------------------------------------------


def test_quick_never_targets_the_committed_results_dir(run_all, tmp_path):
    canonical = (REPO_ROOT / "results").resolve()
    assert run_all.resolve_results_dir(None, False) == (canonical, True, False)
    assert run_all.resolve_results_dir(None, True) == (canonical / "quick", False, True)
    assert run_all.resolve_results_dir(str(canonical), True) == (canonical / "quick", False, True)
    assert run_all.resolve_results_dir(str(tmp_path), True) == (tmp_path.resolve(), False, False)
    assert run_all.resolve_results_dir(str(tmp_path), False) == (tmp_path.resolve(), False, False)


def test_unknown_skip_stage_is_an_argument_error(run_all, capsys):
    with pytest.raises(SystemExit) as exc:
        run_all.main(["--skip", "nope"])
    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_skipping_every_stage_still_imports_all_five_and_writes_the_summary(run_all, tmp_path, capsys):
    assert run_all.main(["--skip", *run_all.SKIPPABLE, "--results", str(tmp_path)]) == 0
    s = json.loads((tmp_path / "run_all_summary.json").read_text())
    assert s["status"] == "ok" and s["failed_stage"] is None and s["quick"] is False
    assert list(s["stages"]) == list(run_all.STAGES)
    assert s["stages"]["imports"]["status"] == "ok"
    assert all(s["stages"][n]["status"] == "skipped" for n in run_all.SKIPPABLE)
    for lib in ("perspective", "QuantLib", "ORE", "skfolio", "nautilus_trader"):
        assert s["versions"][lib]
    out = capsys.readouterr().out
    assert "all five import into one process" in out
    assert "0/7 imports" in out


def test_a_failing_stage_exits_1_records_the_error_and_stops(run_all, tmp_path, monkeypatch, capsys):
    def boom(ctx):
        raise RuntimeError("synthetic failure")

    monkeypatch.setitem(run_all.STAGE_FUNCS, "pricing", boom)
    others = [n for n in run_all.SKIPPABLE if n not in ("pricing", "allocation")]
    monkeypatch.setitem(run_all.STAGE_FUNCS, "allocation",
                        lambda ctx: pytest.fail("a stage ran after the failure"))
    assert run_all.main(["--skip", *others, "--results", str(tmp_path)]) == 1
    s = json.loads((tmp_path / "run_all_summary.json").read_text())
    assert s["status"] == "failed" and s["failed_stage"] == "pricing"
    assert "synthetic failure" in s["error"]
    assert s["stages"]["pricing"]["status"] == "failed"
    assert "allocation" not in s["stages"]
    assert "FAILED at stage 'pricing'" in capsys.readouterr().out


def test_busy_dashboard_port_fails_the_execution_stage_before_the_backtest(run_all, tmp_path,
                                                                          monkeypatch, capsys):
    import socket

    from quantstack.execution import backtest as bt_mod

    monkeypatch.setattr(bt_mod, "main", lambda *a, **k: pytest.fail("backtest started"))
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        others = [n for n in run_all.SKIPPABLE if n != "execution"]
        code = run_all.main(["--serve", "--port", str(port), "--results", str(tmp_path),
                             "--skip", *others])
    assert code == 1
    s = json.loads((tmp_path / "run_all_summary.json").read_text())
    assert s["failed_stage"] == "execution" and "pick another --port" in s["error"]


def test_backtest_cli_forwards_the_sink_to_run_backtest(tmp_path, monkeypatch):
    """run_all streams the live run through backtest.main(..., sink=...)."""
    from quantstack.execution import backtest as bt_mod

    seen = {}

    class Stop(Exception):
        pass

    def fake_run_backtest(*args, **kwargs):
        seen.update(kwargs)
        raise Stop

    monkeypatch.setattr(bt_mod, "run_backtest", fake_run_backtest)
    sink = object()
    with pytest.raises(Stop):
        bt_mod.main(["--symbols", "AAPL,MSFT", "--start", "2018-01-01", "--end", "2018-12-31",
                     "--lookback", "60", "--no-sequencing-experiment",
                     "--results-dir", str(tmp_path / "r")], sink=sink)
    assert seen["sink"] is sink
    assert not (tmp_path / "r").exists()


# --------------------------------------------------------------------------
# end to end
# --------------------------------------------------------------------------


@pytest.mark.slow
def test_run_all_quick_end_to_end(tmp_path):
    out_dir = tmp_path / "quick"
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
    t0 = time.perf_counter()
    proc = subprocess.run([sys.executable, str(SCRIPT), "--quick", "--results", str(out_dir)],
                          capture_output=True, text=True, cwd=tmp_path, env=env, timeout=900)
    wall = time.perf_counter() - t0
    assert proc.returncode == 0, (proc.stdout[-4000:], proc.stderr[-4000:])
    assert "all five import into one process" in proc.stdout

    s = json.loads((out_dir / "run_all_summary.json").read_text())
    assert s["status"] == "ok" and s["quick"] is True and s["canonical_results_dir"] is False
    assert list(s["stages"]) == [
        "imports", "pricing", "allocation", "risk", "bridge", "execution", "positions", "dashboard"]
    assert all(st["status"] == "ok" for st in s["stages"].values()), s["stages"]
    assert all(v is not None and v >= 0 for v in s["stage_seconds"].values())
    assert s["total_seconds"] < wall + 1

    n = {name: st["numbers"] for name, st in s["stages"].items()}
    # risk: 16 paths, tagged files, never the canonical risk_* names
    assert n["risk"]["canonical"] is False and n["risk"]["file_prefix"] == "risk_libor_16_"
    assert n["risk"]["cube"]["samples"] == 16
    assert (out_dir / "risk_libor_16_summary.json").exists()
    assert not (out_dir / "risk_summary.json").exists()
    assert n["risk"]["npv_base"] == pytest.approx(1_609_885.84, abs=0.005)  # NPV needs no paths
    # bridge: canonical committed curves -> the canonical numbers even in quick mode
    assert n["bridge"]["curves_input"] == "results/risk_curves.csv"
    assert n["bridge"]["diff_bp"] == pytest.approx(1.0849, abs=1e-4)
    assert n["bridge"]["this_run_ore_matches_bridge_input"]["npv_abs_diff_eur"] < 0.005
    # execution streamed live; the tables read back over the websocket are non-empty
    tables = s["dashboard_tables_over_websocket"]
    assert tables == n["execution"]["dashboard"]["table_sizes_over_websocket"]
    assert all(v > 0 for v in tables.values()), tables
    assert tables["fills"] == n["execution"]["fills"]
    assert tables["positions"] == len(n["execution"]["universe"]) == 3
    assert n["execution"]["dashboard"]["equity_readback"]["bit_exact_vs_streamed_curve"] is True
    # positions -> ORE, and the dashboard summary replaying this run's files
    assert n["positions"]["n_trades_parsed_by_ore"] == n["positions"]["n_positions"] > 0
    assert n["dashboard"]["replayed_table_sizes"] == tables
    assert n["dashboard"]["summary_kind"] == "ad-hoc"
    # every file this run reports lives under its own results directory
    reported = [*n["risk"]["files"].values(), *n["execution"]["files"].values(),
                n["positions"]["positions_csv"], n["positions"]["ore_portfolio_xml"],
                n["dashboard"]["summary_file"]]
    root = str(out_dir.resolve())
    assert all(str(p).startswith(root) for p in reported), reported
    print(f"run_all --quick: {wall:.1f} s wall, stages {s['stage_seconds']}")
