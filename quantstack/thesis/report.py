"""Reporting for the thesis run: in-sample statistics, the comparison markdown, two figures.

Nothing here runs an engine.  :func:`in_sample_stats` scores a constant
weight vector on a returns window with exactly the formulas of
:mod:`quantstack.allocation.compare` (it calls that module's own helpers);
:func:`comparison_markdown` renders ``thesis_comparison.md`` from the summary
dict that :func:`quantstack.thesis.run.run_thesis` builds; the two ``plot_*``
functions draw on a bare ``Figure`` with the Agg canvas (no pyplot, no global
matplotlib state), in the palette of ``execution/backtest.py``.

Colour follows the scheme in both figures.  The palette validates three
categorical slots all-pairs (blue, orange, aqua); ``own_weights_8020`` is a
variant of ``own_weights``, so it shares the orange and is told apart by a
dashed line (a hatched bar) and its direct label rather than by a fourth hue.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from quantstack.allocation.compare import ZERO_TOL, _compounded_stats, concentration_stats
from quantstack.execution.backtest import LIGHT

TRADING_DAYS = 252


#: scheme -> (display name, short tag for end labels, colour, line style).
SCHEME_STYLE: dict[str, tuple[str, str, str, str]] = {
    "own_weights": ("Own (thesis) weights", "own", LIGHT["s2"], "-"),
    "own_weights_8020": ("Own weights, 80/20 sleeves", "own 80/20", LIGHT["s2"], "--"),
    "equal_weight": ("Equal weight", "equal", LIGHT["s3"], "-"),
    "hrp_optimised": ("HRP (pipeline optimiser)", "HRP", LIGHT["s1"], "-"),
}


def scheme_name(scheme: str) -> str:
    return SCHEME_STYLE.get(scheme, (scheme,))[0]


# --------------------------------------------------------------------------- statistics


def in_sample_stats(returns: pd.DataFrame, weights: Mapping[str, float]) -> dict:
    """A constant weight vector held (rebalanced daily, no costs) over ``returns``.

    Same definitions as :mod:`quantstack.allocation.compare`: ``sharpe`` =
    mean / std(ddof=1) x sqrt(252) (rf = 0); ``annualized_mean_arithmetic`` =
    mean x 252 (not CAGR); ``ann_vol`` = std(ddof=1) x sqrt(252); ``cagr`` and
    ``max_drawdown_compounded`` from ``compare._compounded_stats``; the
    concentration measures from ``compare.concentration_stats``.  ``weights``
    must cover every column of ``returns`` and sum to 1.
    """
    w = pd.Series({c: float(weights[c]) for c in returns.columns})
    if abs(w.sum() - 1.0) > 1e-6:
        raise ValueError(f"weights sum to {w.sum():.6f}; in-sample stats need a fully invested vector")
    daily = returns.to_numpy(dtype=float) @ w.to_numpy()
    mean, std = float(daily.mean()), float(daily.std(ddof=1))
    return {
        "annualized_mean_arithmetic": mean * TRADING_DAYS,
        "ann_vol": std * math.sqrt(TRADING_DAYS),
        "sharpe": mean / std * math.sqrt(TRADING_DAYS) if std > 0 else float("nan"),
        **_compounded_stats(daily),
        **concentration_stats(w, ZERO_TOL),
        "n_days": int(len(daily)),
    }


def sharpe_rf(cagr: float | None, ann_vol: float | None, rf: float) -> float:
    """The thesis's Sharpe convention: ``(CAGR - rf) / annualised vol`` (NaN when undefined)."""
    if cagr is None or ann_vol is None or not ann_vol > 0 or not math.isfinite(cagr):
        return float("nan")
    return (cagr - rf) / ann_vol


def top_weights(weights: Mapping[str, float], n: int = 10) -> list[tuple[str, float]]:
    """The ``n`` largest weights, ties broken by ticker (deterministic)."""
    return sorted(((str(t), float(w)) for t, w in weights.items()), key=lambda kv: (-kv[1], kv[0]))[:n]


# --------------------------------------------------------------------------- markdown


def _pct(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{100 * x:.{nd}f}%"


def _num(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:,.{nd}f}"


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def _metrics_columns(summary: dict) -> list[tuple[str, dict]]:
    """(column title, metrics dict) for the comparison table, in display order.

    The schemes that ran, then the engine's equal-weight benchmark (only when
    the ``equal_weight`` scheme did not run: otherwise it *is* that column),
    then the pandas buy-and-hold.
    """
    ok = [s for s, r in summary["schemes"].items() if r.get("status") == "ok"]
    cols = [(scheme_name(s), summary["schemes"][s]) for s in ok]
    bench = summary.get("benchmarks") or {}
    if bench.get("equal_engine") and "equal_weight" not in ok:
        cols.append(("Equal weight, engine benchmark", bench["equal_engine"]))
    if bench.get("equal_pandas"):
        cols.append(("Equal weight, pandas buy-and-hold", bench["equal_pandas"]))
    return cols


def _traded(m: dict, text) -> str:
    return "none (never trades)" if m.get("never_trades") else text(m)


def _metrics_table(summary: dict) -> list[str]:
    cols = _metrics_columns(summary)
    cur, rf = summary["config"]["currency"], summary["config"]["thesis_rf"]
    book = summary["config"]["book_value"]
    rows = [
        (f"Final equity ({cur}, {book:,.0f} book)", lambda m: _num(m.get("final_equity_book"))),
        ("Total return", lambda m: _pct(m.get("total_return"))),
        ("CAGR", lambda m: _pct(m.get("cagr"))),
        ("Annualised volatility", lambda m: _pct(m.get("ann_vol"))),
        ("Sharpe, rf = 0 (engine)", lambda m: _num(m.get("sharpe"))),
        (f"Sharpe, rf = {100 * rf:g}% (thesis: (CAGR - rf) / vol)", lambda m: _num(m.get("sharpe_rf_thesis"))),
        ("Max drawdown", lambda m: _pct(m.get("max_drawdown"))),
        ("Max drawdown peak to trough", lambda m: (f"{m['max_drawdown_peak']} to {m['max_drawdown_trough']}"
                                                   if m.get("max_drawdown_peak") else "n/a")),
        ("One-way turnover per year",
         lambda m: _traded(m, lambda m: _pct(m.get("turnover_annual_oneway"), 1))),
        ("Fills / denied / rejected",
         lambda m: _traded(m, lambda m: f"{m.get('fills', 'n/a')} / {m.get('denied', 'n/a')} / "
                                        f"{m.get('rejections', 'n/a')}")),
        ("Names held at the end",
         lambda m: "all" if m.get("never_trades") else (f"{m['n_names_held_at_end']} of {m['n_names']}"
                                                        if "n_names_held_at_end" in m else "n/a")),
    ]
    return _table([""] + [c for c, _ in cols], [[label] + [f(m) for _, m in cols] for label, f in rows])


def _comparators_section(summary: dict) -> list[str]:
    comp = summary.get("thesis_comparators") or {}
    if not comp.get("rows"):
        return []
    w0, w1 = comp["window"]
    lines = ["## Thesis comparators", "",
             f"The thesis's own figures for {w0} to {w1} (Sharpe with rf = {100 * comp['rf']:g}%, "
             "drawdowns as positive losses), from its `analysis_results.json`:", ""]
    lines += _table(["Series", "Convention", "CAGR", "Volatility", "Sharpe (thesis)", "Max drawdown", "Source"],
                    [[r["series"], r["convention"], _pct(r["cagr"]), _pct(r["ann_vol"]),
                      _num(r["sharpe_rf_thesis"]), _pct(r["max_drawdown"]), f"`{r['source']}`"]
                     for r in comp["rows"]])
    w = summary["window"]
    same = w.get("first_fill_date") == w0 and w["last_bar"] == w1
    lines += ["", ("This run trades the same window, so the comparison is like for like apart from:" if same else
                   f"This run trades {w.get('first_fill_date')} to {w['last_bar']}, not the thesis window, so "
                   "these figures are context only. The differences that remain even on the same window:"), ""]
    lines += [f"- {d}" for d in comp["structural_differences"]]
    return lines + [""]


def _allocation_table(alloc: dict) -> list[str]:
    names = {"thesis_w_renormalised": "Own (thesis), renormalised", "thesis_w_8020": "Own, 80/20 sleeves",
             "equal_w": "Equal weight", "hrp_w": "HRP", "max_sharpe_w": "Max Sharpe (sample cov)",
             "inv_var_w": "Inverse variance"}
    rows = []
    for key, label in names.items():
        st = alloc["stats"].get(key)
        if st is None:
            rows.append([label, "failed: " + str(alloc["errors"].get(key, "not run"))[:120], "", "", "", "", "", ""])
            continue
        rows.append([label, _pct(st["annualized_mean_arithmetic"]), _pct(st["cagr"]), _pct(st["ann_vol"]),
                     _num(st["sharpe"]), _pct(st["max_drawdown_compounded"]), _num(st["effective_n"], 1),
                     _pct(st["max_weight"], 1)])
    return _table(["Weight vector", "Mean return (arith., ann.)", "CAGR", "Volatility", "Sharpe (rf = 0)",
                   "Max drawdown", "Effective N", "Largest weight"], rows)


def _top_weights_table(summary: dict, n: int = 10) -> list[str]:
    ranked = {s: top_weights(v, n) for s, v in summary["weights_for_report"].items()
              if v and s != "equal_weight"}
    if not ranked:
        return ["(no weights to show)"]
    heads = {"own_weights": "Own (thesis), renormalised", "own_weights_8020": "Own, 80/20 sleeves",
             "hrp_optimised": "HRP, mean over the engine's rebalances"}
    rows = []
    for i in range(max(len(v) for v in ranked.values())):
        row = [str(i + 1)]
        for v in ranked.values():
            row.append(f"{v[i][0]} {_pct(v[i][1])}" if i < len(v) else "")
        rows.append(row)
    return _table(["Rank"] + [heads.get(s, s) for s in ranked], rows)


def _split_table(summary: dict) -> list[str]:
    rows = []
    for s, r in summary["schemes"].items():
        split = r.get("intended_sleeve_split")
        if split:
            rows.append([scheme_name(s), _pct(split.get("core"), 1), _pct(split.get("moonshot"), 1),
                         r.get("intended_sleeve_split_basis", "")])
    return _table(["Scheme", "Core", "Moonshot", "Basis"], rows) if rows else []


def _tracking_section(summary: dict) -> list[str]:
    """``## Target vs achieved weights``: the engine's ``weight_tracking`` per scheme,
    and the whole-unit check at the first rebalance."""
    lines = ["## Target vs achieved weights", ""]
    ok = {s: r for s, r in summary["schemes"].items() if r.get("status") == "ok"}
    tracked = {s: r["target_vs_achieved"] for s, r in ok.items() if r.get("target_vs_achieved")}
    if not tracked:
        lines += ["The engine did not report achieved weights for these runs, so only the whole-unit check "
                  "below is shown.", ""]
    else:
        lines += ["Achieved weight = shares x close / equity right after each rebalance's fills; the gap is "
                  "measured against investment cap x target (the rest is the cash buffer).", ""]
    for s, t in tracked.items():
        below = t["names_below_half_target"]
        lines += [f"**{scheme_name(s)}** over {t['n_rebalances']} rebalances: mean absolute gap "
                  f"{_pct(t['mean_abs_gap'], 3)} per name, largest {_pct(t['max_abs_gap'], 3)} "
                  f"({t['max_abs_gap_symbol']}, {t['max_abs_gap_date']}); {_pct(t['mean_invested_fraction'])} "
                  f"of equity invested after rebalancing; {len(below)} name(s) held at under half their target"
                  + (f" ({', '.join(below)})." if below else ".")
                  + (f" Per rebalance: `{t['achieved_csv']}`." if t.get("achieved_csv") else ""), ""]
        if t["max_abs_gap"] >= 1e-4:  # below 1 bp everywhere the table is rounding noise
            lines += _table(["Ticker", "Cap x target (mean)", "Achieved (mean)", "Mean abs gap", "Max abs gap"],
                            [[g["ticker"], _pct(g["mean_capped_target"], 3), _pct(g["mean_achieved"], 3),
                              _pct(g["mean_abs_gap"], 3), _pct(g["max_abs_gap"], 3)] for g in t["largest_gaps"]])
            lines.append("")
    units = summary.get("whole_unit_check") or {}
    prices = summary.get("engine_prices") or {}
    diag = prices.get("diagnostics") or {}
    top = max(diag.items(), key=lambda kv: kv[1]["engine_max"], default=None)
    highest = f" (the highest here is {top[0]}, up to {top[1]['engine_max']:,.0f} per share)" if top else ""
    level = "rescaled" if prices.get("rescaled") else "raw GBP total-return"
    lines += [f"The engine trades whole shares at the {level} levels{highest}, so a high-priced name with a "
              "small weight lands under its target, and one whose target is worth less than a share is not held. "
              f"At the first rebalance ({units.get('date', 'n/a')}, {units.get('deployable', float('nan')):,.0f} "
              "deployable in engine units):", ""]
    for s, u in (units.get("schemes") or {}).items():
        zero = ", ".join(f"{z['ticker']} (target {z['target_value']:,.0f} at {z['price']:,.2f} per share)"
                         for z in u["zero_units"]) or "none"
        lines += [f"- {scheme_name(s)}: no share for {zero}; "
                  f"1 or 2 shares for {', '.join(u['under_3_units']) or 'none'}."]
    return lines + [""]


def _data_section(summary: dict) -> list[str]:
    pc, ep, reps = summary["panel_check"], summary["engine_prices"], summary["repairs"]
    lines = ["## Data", ""]
    if pc.get("manifest_match"):
        lines.append(f"- `{pc['file']}` ({pc['shape'][0]} rows x {pc['shape'][1]} columns) matches "
                     f"`{pc['manifest']}` (sha256 `{pc['sha256'][:12]}...`, as of {pc['as_of']}).")
    else:
        lines.append(f"- `{pc['file']}` sha256 `{pc['sha256'][:12]}...`: {pc.get('warning') or 'not verified'}.")
    lines.append("- The levels are a GBP total-return index (dividends reinvested, FX applied), not share prices; "
                 "only the holding columns are used.")
    if ep.get("rescaled"):
        rc = ep["rescale_check"]
        lines.append(f"- Each column is rescaled so its minimum over the window is {rc['floor']:g} and rounded to "
                     f"{rc['decimals']} decimals; daily returns move by at most "
                     f"{rc['max_abs_return_diff_after_rounding']:.1e} (before rounding "
                     f"{rc['max_abs_return_diff_unrounded']:.1e}).")
    else:
        lines.append("- Levels are passed to the engine unrescaled (`--no-rescale`).")
    applied = [r for r in reps if r.get("applied") and r["ticker"] in summary["universe"]["included"]]
    if reps and not applied:
        lines.append("- No repair applies to the names in this run.")
    elif not reps:
        lines.append("- Repairs are off (`--no-repairs`).")
    lines.append("")
    if applied:
        lines += _table(["Repair", "Levels before the date divided by", "Return that day", "Verified", "Why"],
                        [[f"{r['ticker']} {r['date']}", _num(r["factor"], 4),
                          f"{_pct(r['return_before'])} to {_pct(r['return_after'])}", r["verified"], r["reason"]]
                         for r in applied])
        lines.append("")
    return lines


def comparison_markdown(summary: dict) -> str:
    """``thesis_comparison.md``: the human-readable side-by-side of a thesis run."""
    w, cfg, uni = summary["window"], summary["config"], summary["universe"]
    preset = summary.get("preset") or {}
    exc = summary["exclusions"]
    split = uni["sleeve_split"]
    exact = bool(preset.get("matches_preset")) and not cfg.get("tickers_subset")
    title = preset["label"] if preset and exact else "custom window" + (
        f" (from preset `{preset['name']}`)" if preset else "")
    user_exc = cfg.get("exclude") or []
    if user_exc:
        title = f"SENSITIVITY, {title}, without {', '.join(user_exc)}"
    lines = [
        f"# Thesis portfolio: {title}",
        "",
        "Generated by `python -m quantstack.thesis.run`"
        + (f" (preset `{preset['name']}`)" if preset.get("name") else "")
        + "; every number comes from `thesis_summary.json` in this folder.",
        "",
    ]
    if user_exc:
        lines += [f"**Sensitivity run.** {', '.join(user_exc)} excluded by user (`--exclude`); every other "
                  "setting is as below. Compare with the run without `--exclude`, not with the thesis.", ""]
    if preset and exact:
        lines += [preset["description"], ""]
    elif preset:
        lines += [f"The window, warm-up or names differ from preset `{preset['name']}` (`--quick` or an "
                  "override), so its description and the thesis comparators do not apply as such.", ""]
    lines += [
        "## Window",
        "",
        f"- Price window {w['first_bar']} to {w['last_bar']} ({w['trading_days']} trading days; "
        f"requested {w['start']} to {w['end']}).",
        f"- The first {cfg['lookback_bars']} bars warm the strategy up; it first trades on "
        f"{w.get('first_fill_date') or 'n/a'} ({_num(w.get('traded_years'))} years to the last bar) and "
        f"rebalances every {cfg['rebalance_every']} trading days.",
        f"- The engine trades a {cfg['currency']} {cfg['starting_cash']:,.0f} book in whole shares, "
        f"{_pct(cfg['investment_cap'], 0)} of equity deployed at each rebalance (the thesis holds 0.376% cash). "
        f"Equity is reported scaled to the {cfg['currency']} {cfg['book_value']:,.0f} thesis book "
        f"(x {cfg['equity_scale']:g}); returns and ratios do not depend on the scale.",
        f"- Metrics run from the first fill to {w['last_bar']}.",
        "",
    ]
    lines += _data_section(summary)
    lines += [
        "## Universe",
        "",
        f"- {uni['n_included']} of {uni['n_universe']} holdings have usable prices over the whole window "
        f"({uni['n_excluded']} excluded, below): core {uni['sleeve_counts']['core']}, "
        f"moonshot {uni['sleeve_counts']['moonshot']}.",
        f"- Thesis sleeve split {_pct(split['thesis']['core'], 1)} / {_pct(split['thesis']['moonshot'], 1)} "
        f"(core / moonshot); renormalised over the included names it becomes {_pct(split['after']['core'], 1)} / "
        f"{_pct(split['after']['moonshot'], 1)} (excluded weight spread pro rata, so the survivors keep their "
        "thesis proportions).",
        f"- Weight of the excluded names in the thesis: {_pct(uni['excluded_weight_total'], 1)} of the book.",
        f"- Forward-filled levels: {uni['n_filled_cells']}"
        + (f" ({', '.join(f'{t} {n}' for t, n in uni['filled_cells'].items())})" if uni["filled_cells"] else "")
        + f"; gaps of at most {cfg['max_ffill_gap']} bars, never back-filled"
        + (", strict calendar" if cfg["strict_calendar"] else "") + ".",
        "",
    ]
    split_rows = _split_table(summary)
    if split_rows:
        lines += ["Intended sleeve split per scheme:", ""] + split_rows + [""]
    if exc:
        lines += ["### Excluded", ""]
        lines += _table(["Ticker", "Sleeve", "Thesis weight", "First level", "Reason"],
                        [[e["ticker"], e.get("sleeve") or "", _pct(e.get("weight_total"), 3),
                          e.get("first_valid") or "none", e["detail"]] for e in exc])
        lines.append("")
    lines += ["## Results", ""]
    lines += _metrics_table(summary)
    lines += [""]
    chk = summary.get("checks", {})
    if chk.get("equal_engine_benchmark_final_equity"):
        same = "identical" if chk.get("equal_engine_benchmark_consistent") else "NOT identical"
        lines += [f"Every run re-ran the engine's equal-weight benchmark on the same data; its final equity is "
                  f"{same} across the {len(chk['equal_engine_benchmark_final_equity'])} runs. "
                  "The equal-weight scheme *is* that benchmark.", ""]
    failed = {s: r for s, r in summary["schemes"].items() if r.get("status") != "ok"}
    for s, r in failed.items():
        lines += [f"**{s} failed:** {r.get('error')}", ""]
    lines += ["![Equity from first fill](figures/thesis_equity.png)", ""]
    lines += _comparators_section(summary)
    lines += ["## Largest weights", ""]
    lines += _top_weights_table(summary)
    eq = summary["weights_for_report"].get("equal_weight")
    if eq:
        lines += ["", f"Equal weight holds every included name at {_pct(1 / len(eq), 3)}."]
    lines += ["", "![Target weights by scheme](figures/thesis_weights.png)", ""]
    lines += _tracking_section(summary)
    alloc = summary["allocation"]
    lines += ["## Allocation stage (in-sample)", "",
              f"Each weight vector fitted (where it is fitted at all) on the whole window's daily returns "
              f"({alloc['window']['first_return']} to {alloc['window']['last_return']}, "
              f"{alloc['window']['n_days']} days) and held constant, rebalanced daily, no costs. In-sample by "
              "construction: the HRP and Max Sharpe rows saw the returns they are scored on.", ""]
    lines += _allocation_table(alloc)
    lines += ["", "## Caveats", ""]
    lines += [f"- {c}" for c in summary["caveats"]]
    dash = summary.get("dashboard") or {}
    if dash:
        lines += ["", "## Dashboard replay", ""]
        lines += [f"- {s}: {d.get('status')}"
                  + (f", tables {d['table_sizes_after_load']}" if d.get("table_sizes_after_load") else "")
                  + (f" ({d['error']})" if d.get("error") else "") for s, d in dash.items()]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- figures


def _money_ticks(lo: float, hi: float, max_ticks: int = 7) -> list[float]:
    """Round-number ticks spanning [lo, hi] on a log axis.

    Wide ranges: 1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8 x 10^k.  Narrow ranges
    (fewer than three of those inside): evenly spaced steps of 1, 2, 2.5 or 5
    x 10^k, so a curve that moves 20% still gets labelled gridlines.
    """
    mantissas = (1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8)
    k0, k1 = int(math.floor(math.log10(lo))), int(math.ceil(math.log10(hi)))
    cands = [m * 10 ** k for k in range(k0, k1 + 1) for m in mantissas if lo <= m * 10 ** k <= hi]
    if len(cands) < 3:
        k = math.floor(math.log10((hi - lo) / max_ticks))
        step = next(m * 10 ** k for m in (1, 2, 2.5, 5, 10) if (hi - lo) / (m * 10 ** k) <= max_ticks)
        cands = [step * i for i in range(math.ceil(lo / step), math.floor(hi / step) + 1)]
    while len(cands) > max_ticks:
        cands = cands[::2]
    return cands


def _money(v: float, symbol: str) -> str:
    return f"{symbol}{v / 1e6:.2f}M" if v >= 1e6 else f"{symbol}{v / 1e3:.0f}k"


def plot_thesis_equity(curves: pd.DataFrame, first_fill: pd.Timestamp, path: Path,
                       symbol: str = "£", title: str = "") -> Path:
    """The schemes' equity from the first fill on a log scale, with an underwater panel.

    ``curves`` has one ``equity_<scheme>`` column per scheme (keys of
    :data:`SCHEME_STYLE`).  Legend plus direct end labels that carry the
    scheme's short tag, so identity never rests on colour alone (the aqua is
    below 3:1 contrast on the surface, and the two own-weight lines share a
    hue).  Same look as ``execution.backtest.plot_equity``.
    """
    import matplotlib
    import matplotlib.dates as mdates
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator, PercentFormatter

    c = LIGHT
    ff = pd.Timestamp(first_fill)
    df = curves.loc[ff - pd.Timedelta(days=45):]
    series = [(f"equity_{s}", *SCHEME_STYLE[s]) for s in SCHEME_STYLE if f"equity_{s}" in df.columns]
    style = {"font.size": 9, "axes.edgecolor": c["text2"], "axes.labelcolor": c["text2"],
             "xtick.color": c["text2"], "ytick.color": c["text2"]}
    with matplotlib.rc_context(style):
        fig = Figure(figsize=(9, 6.2))
        FigureCanvasAgg(fig)
        ax, axd = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 1.3], "hspace": 0.08})
        fig.patch.set_facecolor(c["surface"])
        for a in (ax, axd):
            a.set_facecolor(c["surface"])
            a.grid(True, color=c["grid"], linewidth=0.6)
            for side in ("top", "right"):
                a.spines[side].set_visible(False)
        for s0, s1, label in (("2020-02-19", "2020-03-23", "COVID crash"),
                              ("2022-01-03", "2022-10-12", "2022 bear market")):
            if pd.Timestamp(s1) >= df.index[0] and pd.Timestamp(s0) <= df.index[-1]:
                x0 = max(pd.Timestamp(s0), df.index[0])
                for a in (ax, axd):
                    a.axvspan(x0, pd.Timestamp(s1), color=c["shade"], zorder=0)
                ax.text(x0, 1.0, " " + label, transform=ax.get_xaxis_transform(),
                        va="top", ha="left", fontsize=8, color=c["text2"])
        ends = []
        for col, label, tag, color, ls in series:
            s = df[col].dropna()
            ax.plot(s.index, s.values, color=color, linewidth=1.6, linestyle=ls, label=label)
            ends.append((float(np.log10(s.iloc[-1])), float(s.iloc[-1]), s.index[-1], color, tag, ls))
            tail = s.loc[ff:]
            dd = tail / tail.cummax() - 1.0
            axd.plot(dd.index, dd.values, color=color, linewidth=1.2, linestyle=ls)
        vals = df[[s[0] for s in series]]
        lo, hi = float(vals.min().min()), float(vals.max().max())
        gap = 0.045 * max(np.log10(hi) - np.log10(lo), 1e-3)
        placed: list[float] = []
        span = df.index[-1] - df.index[0]
        for y_log, v, x, color, tag, ls in sorted(ends, key=lambda e: e[0]):
            y = max([y_log] + [p + gap for p in placed])
            placed.append(y)
            ax.plot([x + span * 0.012], [10 ** y], marker="o", markersize=5, clip_on=False, zorder=5,
                    color=color, markerfacecolor=color if ls == "-" else c["surface"], markeredgewidth=1.4)
            ax.annotate(f"{_money(v, symbol)} {tag}", xy=(x + span * 0.022, 10 ** y), va="center", ha="left",
                        fontsize=8, color=c["text"], annotation_clip=False)
        ax.axvline(ff, color=c["text2"], linewidth=0.8, linestyle=":")
        ax.set_yscale("log")
        ax.set_ylim(lo * 0.97, hi * 1.03)
        ax.yaxis.set_major_locator(FixedLocator(_money_ticks(lo * 0.97, hi * 1.03)))
        ax.yaxis.set_minor_locator(NullLocator())
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _money(v, symbol)))
        ax.set_ylabel("Equity (log scale)")
        ax.legend(loc="upper left", bbox_to_anchor=(0.0, 0.93), frameon=False, fontsize=8, labelcolor=c["text"])
        ax.set_title(title or "Thesis portfolio in NautilusTrader: equity from first fill",
                     loc="left", fontsize=11, color=c["text"])
        axd.set_ylabel("Drawdown")
        axd.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
        axd.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=8))
        axd.xaxis.set_major_formatter(mdates.ConciseDateFormatter(axd.xaxis.get_major_locator()))
        axd.set_xlabel("Date")
        fig.subplots_adjust(left=0.1, right=0.85, top=0.93, bottom=0.08)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=120, facecolor=c["surface"])
    return path


def plot_thesis_weights(panels: Mapping[str, dict], order: Sequence[str], sleeves: Mapping[str, str],
                        path: Path, title: str = "") -> Path:
    """Small multiples of horizontal bars: one panel per scheme, one row per ticker.

    ``panels`` maps a scheme (key of :data:`SCHEME_STYLE`) to ``{"weights":
    Series, "low": Series | None, "high": Series | None, "label": str}``;
    ``low``/``high`` draw a min-max whisker (HRP's range across rebalances).
    Rows follow ``order`` top to bottom (the caller sorts by sleeve, then
    thesis weight); a rule separates the sleeves.  All panels share one
    percentage x-axis, so bar lengths compare across schemes.
    """
    import matplotlib
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.ticker import PercentFormatter

    c = LIGHT
    n = len(order)
    y = np.arange(n)
    xmax = max(float(max(p["weights"].max(), (p["high"].max() if p.get("high") is not None else 0.0)))
               for p in panels.values())
    style = {"font.size": 8, "axes.edgecolor": c["text2"], "axes.labelcolor": c["text2"],
             "xtick.color": c["text2"], "ytick.color": c["text2"], "hatch.color": c["surface"]}
    height = 1.3 + 0.17 * n  # ~0.17 in per ticker row
    with matplotlib.rc_context(style):
        fig = Figure(figsize=(3.0 * len(panels) + 1.4, height))
        FigureCanvasAgg(fig)
        axes = fig.subplots(1, len(panels), sharey=True, sharex=True, squeeze=False)[0]
        fig.patch.set_facecolor(c["surface"])
        boundary = next((i for i in range(1, n) if sleeves[order[i]] != sleeves[order[i - 1]]), None)
        for ax, (scheme, p) in zip(axes, panels.items()):
            color = SCHEME_STYLE[scheme][2]
            w = p["weights"].reindex(order).fillna(0.0).to_numpy()
            ax.set_facecolor(c["surface"])
            hatch = "////" if SCHEME_STYLE[scheme][3] != "-" else None  # the dashed variant, as texture
            ax.barh(y, w, height=0.72, color=color, zorder=2, hatch=hatch, linewidth=0)
            if p.get("low") is not None and p.get("high") is not None:
                lo_, hi_ = p["low"].reindex(order).to_numpy(), p["high"].reindex(order).to_numpy()
                ax.hlines(y, lo_, hi_, color=c["text"], linewidth=0.8, zorder=3)
            ax.grid(True, axis="x", color=c["grid"], linewidth=0.6, zorder=0)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
            if boundary is not None:
                ax.axhline(boundary - 0.5, color=c["text2"], linewidth=0.8, linestyle=":", zorder=1)
            ax.set_title(p["label"], loc="left", fontsize=9, color=c["text"])
            ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
            ax.set_xlim(0, xmax * 1.05)
            ax.tick_params(axis="y", length=0)
        axes[0].set_yticks(y)
        axes[0].set_yticklabels(order, fontsize=7, color=c["text"])
        axes[0].set_ylim(n - 0.4, -0.6)
        if boundary is not None:  # name the sleeves on the panel with the shortest bars (1/N if drawn)
            host = axes[list(panels).index("equal_weight")] if "equal_weight" in panels else axes[-1]
            for yy, name in ((boundary - 0.9, sleeves[order[0]]), (boundary - 0.1, sleeves[order[boundary]])):
                host.text(1.0, yy, name + " sleeve", transform=host.get_yaxis_transform(),
                          ha="right", va="bottom" if yy < boundary - 0.5 else "top", fontsize=7,
                          color=c["text2"])
        fig.suptitle(title or "Target weights by scheme (sorted by sleeve, then thesis weight)",
                     x=0.01, y=1 - 0.12 / height, ha="left", va="top", fontsize=11, color=c["text"])
        fig.subplots_adjust(left=0.1, right=0.98, top=1 - 0.75 / height, bottom=0.45 / height, wspace=0.08)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=120, facecolor=c["surface"])
    return path


__all__ = [
    "SCHEME_STYLE",
    "comparison_markdown",
    "in_sample_stats",
    "plot_thesis_equity",
    "plot_thesis_weights",
    "scheme_name",
    "sharpe_rf",
    "top_weights",
]
