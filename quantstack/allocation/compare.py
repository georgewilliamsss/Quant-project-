"""Sizing: skfolio's Max-Sharpe vs Hierarchical Risk Parity, and the fake precision
in between.

This module reproduces the "Five Repos, One Engine" article's allocation section.
It fits two long-only allocators on skfolio's bundled 20-name S&P 500 price panel
and measures how *concentrated* each one is. Max Sharpe on the sample covariance
is known for putting almost the whole book into a handful of names it can barely
tell apart from noise. The module then checks whether that extra "precision"
earns anything out of sample.

The article's headline point, and the reason for the module's name, is that
the sample-covariance Max-Sharpe optimizer treats a noisy in-sample covariance
estimate as if it were exact. So it "confidently" concentrates into about 8 of
20 names, and that confidence buys essentially nothing out of sample compared
with HRP. HRP never claims to know the precise optimum and diversifies by
construction.

Versions: we run skfolio 1.4.0; the article used 1.0.2. No API change was
needed between the two. ``ObjectiveFunction`` is imported from
``skfolio.optimization`` in both versions (see :mod:`.weights`). Running this
same comparison against the skfolio 1.0.2 *source* (on this venv's numpy /
scikit-learn / cvxpy) gives the same numbers to at least 4 decimals, for the
fixed split and the walk-forward alike. So there is no version gap to explain.
The actual figures are in the docstring of :func:`main`.

Both allocators are fitted through the one adapter the rest of the stack is
allowed to use, :func:`quantstack.contracts.fit_weights`. It turns any
scikit-learn-style ``estimator.fit(returns) -> estimator.weights_`` object into
a validated :class:`quantstack.contracts.Weights` mapping, and leaves the
estimator fitted, so ``.predict()`` still works for the out-of-sample step.
The reusable allocators (``hrp_weights``, ``equal_weight``, ``build_hrp``,
``build_max_sharpe``) live in the import-light :mod:`.weights` and are
re-exported here.

Measures, stated because skfolio's defaults are *uncompounded*:

* Sharpe = mean / std(ddof=1) * sqrt(252) of daily portfolio returns. This is
  skfolio's ``annualized_sharpe_ratio`` and the article's definition (they
  agree to about 1e-15).
* ``annualized_mean_arithmetic`` = mean daily return * 252 (skfolio's
  ``annualized_mean``). It is **not** CAGR, so ``cagr`` is reported next to it.
* ``max_drawdown_uncompounded`` is skfolio's default ``max_drawdown``: the
  drawdown of the cumulative *sum* of returns. ``max_drawdown_compounded`` is
  the peak-to-trough loss of compounded wealth (what most readers mean). On
  2020-2022 the two measures rank the allocators differently, so both are
  reported.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

import skfolio
from skfolio.datasets import load_sp500_dataset
from skfolio.model_selection import WalkForward, cross_val_predict
from skfolio.preprocessing import prices_to_returns

from quantstack.allocation.weights import (
    build_hrp,
    build_max_sharpe,
    equal_weight,
    hrp_weights,
    check_unique_asset_labels,
)
from quantstack.contracts import fit_weights

# --------------------------------------------------------------------------
# Paths, windows, article reference numbers
# --------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"

FIT_START, FIT_END = "2015-01-01", "2019-12-31"
TEST_START, TEST_END = "2020-01-01", "2022-12-31"

ZERO_TOL = 1e-4  # "near-zero" weight threshold used throughout, per the article

WF_TEST_SIZE, WF_TRAIN_SIZE = 252, 756

ARTICLE_SKFOLIO_VERSION = "1.0.2"
ARTICLE = {
    "max_sharpe": {"n_near_zero": 12, "max_weight": 0.266, "effective_n": 5.3, "oos_sharpe": 0.81},
    "hrp": {"n_near_zero": 0, "max_weight": 0.109, "effective_n": 15.5, "oos_sharpe": 0.80},
}
#: Decimal places the article prints each metric to (26.6% -> 3 as a fraction).
ARTICLE_DECIMALS = {"n_near_zero": 0, "max_weight": 3, "effective_n": 1, "oos_sharpe": 2}
#: "Similar OOS Sharpe" means the two allocators' fixed-split OOS Sharpes differ
#: by less than this.
STORY_MAX_OOS_SHARPE_GAP = 0.1

__all__ = [
    "build_hrp",
    "build_max_sharpe",
    "equal_weight",
    "hrp_weights",
    "load_returns",
    "fit_test_split",
    "concentration_stats",
    "oos_portfolio_stats",
    "fixed_split_comparison",
    "walk_forward_oos_sharpe",
    "walk_forward_report",
    "article_comparison",
    "plot_weights",
    "main",
]


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------


def load_returns() -> pd.DataFrame:
    """Load the bundled 20-large-cap daily price panel (1990-2022) and convert
    to simple returns via skfolio's own helper, exactly as the article does."""
    prices = load_sp500_dataset()
    return prices_to_returns(prices)


def fit_test_split(returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The article's in-sample fit window (2015-2019) and out-of-sample test
    window (2020-2022), sliced from the full returns panel."""
    fit = returns.loc[FIT_START:FIT_END]
    test = returns.loc[TEST_START:TEST_END]
    return fit, test


# --------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------


def concentration_stats(weights: pd.Series, zero_tol: float = ZERO_TOL) -> dict:
    """Number of (near-)zero holdings, max weight, and the effective number of
    names (``1 / sum(w**2)``, the inverse Herfindahl index). These are the
    article's three concentration diagnostics."""
    w = weights.to_numpy(dtype=float)
    return {
        "n_near_zero": int((w < zero_tol).sum()),
        "n_assets": int(len(w)),
        "max_weight": float(w.max()),
        "effective_n": float(1.0 / np.sum(w**2)),
    }


def _compounded_stats(daily: np.ndarray, periods_per_year: int = 252) -> dict:
    """CAGR and max drawdown of compounded wealth ``prod(1 + r)``, starting
    from wealth 1.0 (so a loss on day one counts as a drawdown)."""
    wealth = np.cumprod(1.0 + daily)
    cagr = wealth[-1] ** (periods_per_year / len(daily)) - 1.0
    peak = np.maximum.accumulate(np.concatenate(([1.0], wealth)))[1:]
    return {"cagr": float(cagr), "max_drawdown_compounded": float((1.0 - wealth / peak).max())}


def oos_portfolio_stats(fitted_estimator, test_returns: pd.DataFrame) -> dict:
    """Apply a fitted estimator's ``predict`` to the test returns and report
    out-of-sample performance.

    ``predict`` is part of skfolio's scikit-learn-style contract: once fitted,
    an estimator *is* a weight vector, and ``predict`` re-applies it to new
    data, giving a ``skfolio.Portfolio``.

    Keys (see the module docstring for why both flavours are reported):

    * ``annualized_sharpe``: skfolio's ``annualized_sharpe_ratio``, i.e.
      mean / std(ddof=1) * sqrt(252). ``tests/test_allocation.py`` checks it
      against the hand-computed value.
    * ``annualized_mean_arithmetic``: mean daily return * 252 (skfolio's
      ``annualized_mean``, non-compounded). Not CAGR.
    * ``cagr``: compounded annual growth rate of wealth.
    * ``max_drawdown_uncompounded``: skfolio's default ``max_drawdown``, taken
      on cumulative *summed* returns.
    * ``max_drawdown_compounded``: peak-to-trough loss of compounded wealth.
      This equals ``Portfolio(..., compounded=True).max_drawdown``.
    """
    portfolio = fitted_estimator.predict(test_returns)
    daily = np.asarray(portfolio.returns, dtype=float)
    return {
        "annualized_sharpe": float(portfolio.annualized_sharpe_ratio),
        "annualized_mean_arithmetic": float(portfolio.annualized_mean),
        "max_drawdown_uncompounded": float(portfolio.max_drawdown),
        **_compounded_stats(daily),
        "n_days": int(len(daily)),
    }


def fixed_split_comparison(returns: pd.DataFrame) -> dict:
    """The article's main experiment: fit both allocators on 2015-2019 through
    the contract adapter, then score them on 2020-2022.

    Returns ``{"weights": {name: pd.Series}, "in_sample": {name: stats},
    "out_of_sample": {name: stats}}`` for ``name`` in ``max_sharpe``, ``hrp``.
    """
    check_unique_asset_labels(returns.columns)
    fit_returns, test_returns = fit_test_split(returns)
    weights, in_sample, out_of_sample = {}, {}, {}
    for name, estimator in (("max_sharpe", build_max_sharpe()), ("hrp", build_hrp())):
        # fit_weights fits the estimator in place and validates the weights
        # (contracts.validate_weights), so ``estimator.predict`` works below.
        w = fit_weights(estimator, fit_returns)
        weights[name] = pd.Series(w, name=f"{name}_w").reindex([str(c) for c in fit_returns.columns])
        in_sample[name] = concentration_stats(weights[name])
        out_of_sample[name] = oos_portfolio_stats(estimator, test_returns)
    return {"weights": weights, "in_sample": in_sample, "out_of_sample": out_of_sample}


def _date(ts) -> str:
    return str(pd.Timestamp(ts).date())


def _walk_forward_variant(returns_full: pd.DataFrame, reduce_test: bool) -> dict:
    """Run ``cross_val_predict`` with ``WalkForward(test_size=252,
    train_size=756, reduce_test=...)`` for both allocators. Returns the
    concatenated OOS Sharpe per allocator plus the actual fold dates."""
    wf = WalkForward(test_size=WF_TEST_SIZE, train_size=WF_TRAIN_SIZE, reduce_test=reduce_test)
    sharpe: dict[str, float] = {}
    folds: list[dict] = []
    for name, estimator in (("max_sharpe", build_max_sharpe()), ("hrp", build_hrp())):
        prediction = cross_val_predict(estimator, returns_full, cv=wf)
        sharpe[name] = float(prediction.annualized_sharpe_ratio)
        spans = [
            (_date(p.observations[0]), _date(p.observations[-1]), int(len(p.returns)))
            for p in prediction.portfolios
        ]
        if not folds:
            folds = [{"oos_start": s, "oos_end": e, "n_days": n, "sharpe": {}} for s, e, n in spans]
        elif [(f["oos_start"], f["oos_end"], f["n_days"]) for f in folds] != spans:
            raise RuntimeError("WalkForward produced different folds for the two allocators")
        for fold, p in zip(folds, prediction.portfolios):
            fold["sharpe"][name] = float(p.annualized_sharpe_ratio)
    return {
        "reduce_test": reduce_test,
        "n_folds": len(folds),
        "n_oos_days": int(sum(f["n_days"] for f in folds)),
        "oos_span": [folds[0]["oos_start"], folds[-1]["oos_end"]],
        "oos_sharpe": sharpe,
        "folds": folds,
    }


def walk_forward_oos_sharpe(returns_full: pd.DataFrame, reduce_test: bool = True) -> dict[str, float]:
    """The scikit-learn contract, demonstrated. ``cross_val_predict`` with a
    ``WalkForward`` splitter treats each skfolio optimizer like any other
    scikit-learn estimator with ``fit``/``predict``. It refits on a rolling
    756-day training block, predicts the next 252-day block, and concatenates
    the OOS blocks into one ``MultiPeriodPortfolio``, whose annualized Sharpe
    is returned per allocator. skfolio optimizers also subclass
    scikit-learn's ``BaseEstimator``, so the same objects drop into a
    ``sklearn.pipeline.Pipeline`` unchanged. We use ``WalkForward`` because it
    actually walks forward through time, which is what "out-of-sample" has to
    mean for a return series.

    ``reduce_test`` matters. On the 2015-2022 panel (2012 rows) there is room
    for 4 full test years after the first 756-day training block, plus 248
    leftover rows:

    * ``reduce_test=False`` (skfolio's default) drops the partial last fold.
      That leaves 4 folds with OOS dates 2018-01-03..2022-01-03 (1008 days),
      so the 2022 bear market is never scored. Result: Max Sharpe 1.39 vs
      HRP 0.90.
    * ``reduce_test=True`` (this function's default) scores the partial fold
      too: 5 folds, OOS 2018-01-03..2022-12-28 (1256 days). Result: 0.86 vs
      0.78. In the 2022 fold alone Max Sharpe scored -0.69 vs HRP +0.22,
      which is where most of the default variant's gap goes.
    """
    return _walk_forward_variant(returns_full, reduce_test)["oos_sharpe"]


def walk_forward_report(returns_full: pd.DataFrame) -> dict:
    """Both ``WalkForward`` variants (see :func:`walk_forward_oos_sharpe`)
    with their real OOS spans and per-fold Sharpes, plus a note built from
    the computed values. The full-coverage variant (``reduce_test=True``) is
    the headline because it scores every row after the first training block.
    """
    full = _walk_forward_variant(returns_full, reduce_test=True)
    default = _walk_forward_variant(returns_full, reduce_test=False)
    dropped = full["folds"][default["n_folds"]:]
    gap_default = default["oos_sharpe"]["max_sharpe"] - default["oos_sharpe"]["hrp"]
    gap_full = full["oos_sharpe"]["max_sharpe"] - full["oos_sharpe"]["hrp"]
    note = (
        f"skfolio's default WalkForward(reduce_test=False) scores {default['n_folds']} folds, "
        f"OOS {default['oos_span'][0]}..{default['oos_span'][1]} ({default['n_oos_days']} days): "
        f"Max Sharpe {default['oos_sharpe']['max_sharpe']:.2f} vs HRP {default['oos_sharpe']['hrp']:.2f}. "
    )
    if dropped:
        d_ms = [f["sharpe"]["max_sharpe"] for f in dropped]
        d_hrp = [f["sharpe"]["hrp"] for f in dropped]
        note += (
            f"It drops the final partial fold ({dropped[0]['oos_start']}..{dropped[-1]['oos_end']}, "
            f"{sum(f['n_days'] for f in dropped)} days), in which Max Sharpe scored "
            f"{', '.join(f'{x:.2f}' for x in d_ms)} vs HRP {', '.join(f'{x:.2f}' for x in d_hrp)}. "
        )
    note += (
        f"With reduce_test=True ({full['n_folds']} folds, OOS {full['oos_span'][0]}..{full['oos_span'][1]}, "
        f"{full['n_oos_days']} days): Max Sharpe {full['oos_sharpe']['max_sharpe']:.2f} vs HRP "
        f"{full['oos_sharpe']['hrp']:.2f}. The Max Sharpe minus HRP gap goes from {gap_default:.2f} "
        f"to {gap_full:.2f} once the final fold is included."
    )
    return {
        "splitter": {
            "class": "skfolio.model_selection.WalkForward",
            "test_size": WF_TEST_SIZE,
            "train_size": WF_TRAIN_SIZE,
        },
        "input_span": [_date(returns_full.index.min()), _date(returns_full.index.max())],
        "input_rows": int(len(returns_full)),
        "headline_variant": "reduce_test_true",
        "variants": {"reduce_test_true": full, "reduce_test_false_default": default},
        "note": note,
    }


def article_comparison(in_sample: dict, out_of_sample: dict) -> dict:
    """Compare the computed numbers with the article's. Every verdict here is
    computed, not typed in.

    * ``matches_article_at_printed_precision``: the computed value, rounded to
      the decimals the article prints, equals the article's value.
    * ``qualitative_story_holds``: Max Sharpe has fewer effective names and
      more near-zero weights than HRP, *and* the fixed-split OOS Sharpes
      differ by less than :data:`STORY_MAX_OOS_SHARPE_GAP`.
    """
    computed = {
        name: {
            "n_near_zero": in_sample[name]["n_near_zero"],
            "max_weight": in_sample[name]["max_weight"],
            "effective_n": in_sample[name]["effective_n"],
            "oos_sharpe": out_of_sample[name]["annualized_sharpe"],
        }
        for name in ARTICLE
    }
    delta = {n: {k: computed[n][k] - ARTICLE[n][k] for k in ARTICLE[n]} for n in ARTICLE}
    matches = {
        n: {
            k: math.isclose(round(computed[n][k], ARTICLE_DECIMALS[k]), ARTICLE[n][k], abs_tol=1e-12)
            for k in ARTICLE[n]
        }
        for n in ARTICLE
    }
    all_match = all(v for m in matches.values() for v in m.values())
    ms, hrp = computed["max_sharpe"], computed["hrp"]
    sharpe_gap = ms["oos_sharpe"] - hrp["oos_sharpe"]
    checks = {
        "max_sharpe_fewer_effective_names": ms["effective_n"] < hrp["effective_n"],
        "max_sharpe_more_near_zero": ms["n_near_zero"] > hrp["n_near_zero"],
        "oos_sharpe_gap_max_sharpe_minus_hrp": sharpe_gap,
        "oos_sharpe_gap_threshold": STORY_MAX_OOS_SHARPE_GAP,
        "oos_sharpe_similar": abs(sharpe_gap) < STORY_MAX_OOS_SHARPE_GAP,
    }
    story = bool(
        checks["max_sharpe_fewer_effective_names"]
        and checks["max_sharpe_more_near_zero"]
        and checks["oos_sharpe_similar"]
    )
    n = in_sample["max_sharpe"]["n_assets"]
    note = (
        f"skfolio {skfolio.__version__} here vs {ARTICLE_SKFOLIO_VERSION} in the article. "
        f"Max Sharpe: {ms['n_near_zero']}/{n} near-zero, max {ms['max_weight']:.1%}, "
        f"effective N {ms['effective_n']:.2f} (article {ARTICLE['max_sharpe']['n_near_zero']}/{n}, "
        f"{ARTICLE['max_sharpe']['max_weight']:.1%}, {ARTICLE['max_sharpe']['effective_n']}). "
        f"HRP: {hrp['n_near_zero']}/{n}, max {hrp['max_weight']:.1%}, effective N {hrp['effective_n']:.2f} "
        f"(article {ARTICLE['hrp']['n_near_zero']}/{n}, {ARTICLE['hrp']['max_weight']:.1%}, "
        f"{ARTICLE['hrp']['effective_n']}). OOS Sharpe {ms['oos_sharpe']:.3f} vs {hrp['oos_sharpe']:.3f} "
        f"(article {ARTICLE['max_sharpe']['oos_sharpe']:.2f} vs {ARTICLE['hrp']['oos_sharpe']:.2f}). "
        + (
            "Every metric matches the article at the precision it prints. "
            if all_match
            else "Not every metric matches the article at the precision it prints (see matches_article_at_printed_precision). "
        )
        + (
            f"The qualitative story holds: Max Sharpe is more concentrated and its OOS Sharpe is within "
            f"{STORY_MAX_OOS_SHARPE_GAP} of HRP's."
            if story
            else "The qualitative story does NOT hold on these numbers (see story_checks)."
        )
    )
    return {
        "article_skfolio_version": ARTICLE_SKFOLIO_VERSION,
        "article": ARTICLE,
        "article_printed_decimals": ARTICLE_DECIMALS,
        "computed": computed,
        "delta_computed_minus_article": delta,
        "matches_article_at_printed_precision": matches,
        "all_match_at_printed_precision": all_match,
        "story_checks": checks,
        "qualitative_story_holds": story,
        "version_note": (
            "Checked by hand, not at runtime: no API change was needed between skfolio 1.0.2 and "
            "1.4.0 (ObjectiveFunction is imported from skfolio.optimization in both), and running "
            "this comparison against the skfolio 1.0.2 source with this venv's numpy/scikit-learn/"
            "cvxpy gives the same numbers to at least 4 decimals."
        ),
        "note": note,
    }


# --------------------------------------------------------------------------
# Figure
# --------------------------------------------------------------------------


# Categorical duo from the house palette (validated colorblind-safe adjacent
# pair, light-mode slots 1 and 2): blue for the "confident" concentrated
# optimizer, orange for the diversifying one.
_COLOR_MAX_SHARPE = "#2a78d6"
_COLOR_HRP = "#eb6834"
_COLOR_GRID = "#d8d7d2"
_COLOR_TEXT = "#3a3a37"


def plot_weights(ms_weights: pd.Series, hrp_weights_: pd.Series, path: Path) -> Path:
    """Grouped bar chart of both weight vectors, sorted by the Max-Sharpe
    weight so the ~12 near-zero holdings sit together on the right and the
    contrast with HRP's full-breadth allocation is visible at a glance.

    matplotlib is imported here, not at module level. Importing this module
    (or :mod:`.weights`) from the execution or dashboard processes should not
    switch the global matplotlib backend as a side effect. The object-oriented
    ``Figure`` API with the Agg canvas renders off-screen without touching
    ``pyplot`` state at all.
    """
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    order = ms_weights.sort_values(ascending=False).index
    ms_sorted = ms_weights.loc[order]
    hrp_sorted = hrp_weights_.loc[order]

    x = np.arange(len(order))
    width = 0.4

    fig = Figure(figsize=(11, 5.5), dpi=150)
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    ax.bar(x - width / 2, ms_sorted.to_numpy() * 100, width, label="Max Sharpe (sample cov)", color=_COLOR_MAX_SHARPE)
    ax.bar(x + width / 2, hrp_sorted.to_numpy() * 100, width, label="Hierarchical Risk Parity", color=_COLOR_HRP)

    ax.axhline(0, color=_COLOR_GRID, linewidth=1, zorder=0)
    ax.set_xticks(x)
    ax.set_xticklabels(order, rotation=45, ha="right", fontsize=9, color=_COLOR_TEXT)
    ax.set_ylabel("Portfolio weight (%)", color=_COLOR_TEXT)
    ax.set_title(
        "skfolio allocators fit on the same 2015-2019 sample: precision vs breadth",
        fontsize=12,
        color=_COLOR_TEXT,
    )
    n_zero = int((ms_sorted.to_numpy() < ZERO_TOL).sum())
    n_zero_hrp = int((hrp_sorted.to_numpy() < ZERO_TOL).sum())
    hrp_text = f"HRP holds all {len(order)}" if n_zero_hrp == 0 else f"HRP zeroes {n_zero_hrp}"
    ax.text(
        0.99,
        0.97,
        f"Max Sharpe zeroes {n_zero}/{len(order)} names; {hrp_text}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=9,
        color=_COLOR_TEXT,
    )
    ax.grid(axis="y", color=_COLOR_GRID, linewidth=0.8, zorder=-1)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    return path


# --------------------------------------------------------------------------
# CLI entry point
# --------------------------------------------------------------------------


def _display_path(path: Path) -> Path | str:
    """Path relative to the repo root for the printed summary, or the path
    itself when it lives elsewhere (e.g. a test pointed the module at
    ``tmp_path``)."""
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


def main() -> dict:
    """Run the full comparison and write the three deliverable files.

    Actual numbers computed here with skfolio 1.4.0. The skfolio 1.0.2 source
    gives the same values to at least 4 decimals, so any difference from the
    article is only its rounding.

        Max Sharpe (in-sample 2015-2019): 12/20 near-zero, max weight 26.60%,
          effective N 5.256   (article: 12/20, 26.6%, 5.3)
        HRP (in-sample 2015-2019):        0/20 near-zero, max weight 10.88%,
          effective N 15.453  (article: 0/20, 10.9%, 15.5)
        Out-of-sample 2020-2022 (754 days), Max Sharpe vs HRP:
          annualized Sharpe             0.807 vs 0.798   (article: 0.81 / 0.80)
          arithmetic mean x 252         22.75% vs 17.66%
          CAGR                          20.64% vs 16.42%
          max drawdown, uncompounded    32.10% vs 32.95%
          max drawdown, compounded      30.43% vs 30.17%  (the ranking flips)
        Walk-forward OOS Sharpe, WalkForward(test=252, train=756), Max Sharpe vs HRP:
          reduce_test=True,  5 folds, 2018-01-03..2022-12-28: 0.861 vs 0.777
          reduce_test=False, 4 folds, 2018-01-03..2022-01-03: 1.394 vs 0.905
          (the default drops the partial 2022 fold: -0.69 vs +0.22)

    The qualitative story holds. Max Sharpe trusts a noisy sample covariance
    and concentrates into 8 of 20 names; HRP diversifies by construction and
    holds all of them. On the fixed split the extra "precision" buys about
    0.01 of OOS Sharpe. Over the full walk-forward it buys about 0.08, and
    only if 2022 is left out does it look like 0.49. The summary JSON computes
    this verdict (``article_comparison.qualitative_story_holds``) instead of
    asserting it.
    """
    t0 = time.perf_counter()
    returns = load_returns()
    fit_returns, _test_returns = fit_test_split(returns)

    fixed = fixed_split_comparison(returns)
    ms_weights, hrp_w = fixed["weights"]["max_sharpe"], fixed["weights"]["hrp"]
    ms_stats, hrp_stats = fixed["in_sample"]["max_sharpe"], fixed["in_sample"]["hrp"]
    ms_oos, hrp_oos = fixed["out_of_sample"]["max_sharpe"], fixed["out_of_sample"]["hrp"]

    returns_2015_2022 = returns.loc[FIT_START:TEST_END]
    wf = walk_forward_report(returns_2015_2022)
    wf_head = wf["variants"][wf["headline_variant"]]
    wf_default = wf["variants"]["reduce_test_false_default"]

    ew = equal_weight(fit_returns)
    if abs(sum(ew.values()) - 1.0) > 1e-9:  # explicit check: survives python -O
        raise RuntimeError(f"equal_weight does not sum to 1: {sum(ew.values())!r}")

    article = article_comparison(fixed["in_sample"], fixed["out_of_sample"])

    # --- outputs -----------------------------------------------------
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    order = ms_weights.sort_values(ascending=False).index
    weights_df = pd.DataFrame(
        {"asset": order, "max_sharpe_w": ms_weights.loc[order].to_numpy(), "hrp_w": hrp_w.loc[order].to_numpy()}
    )
    weights_csv = RESULTS_DIR / "allocation_weights.csv"
    weights_df.to_csv(weights_csv, index=False)

    # No runtime field: every value below is deterministic, so reruns give a
    # byte-identical file. The runtime is printed instead.
    summary = {
        "skfolio_version": skfolio.__version__,
        "dataset": {
            "source": "skfolio.datasets.load_sp500_dataset",
            "n_assets": int(returns.shape[1]),
            "assets": [str(c) for c in returns.columns],
            "full_range": [_date(returns.index.min()), _date(returns.index.max())],
        },
        "fit_window": [FIT_START, FIT_END],
        "fit_span_actual": [_date(fit_returns.index.min()), _date(fit_returns.index.max())],
        "test_window": [TEST_START, TEST_END],
        "zero_tolerance": ZERO_TOL,
        "in_sample": {"max_sharpe": ms_stats, "hrp": hrp_stats},
        "out_of_sample": {"max_sharpe": ms_oos, "hrp": hrp_oos},
        "out_of_sample_measures": {
            "annualized_sharpe": "mean/std(ddof=1)*sqrt(252) of daily returns (skfolio annualized_sharpe_ratio)",
            "annualized_mean_arithmetic": "mean daily return * 252, uncompounded (skfolio annualized_mean); not CAGR",
            "cagr": "(prod(1+r))**(252/n_days) - 1",
            "max_drawdown_uncompounded": "skfolio default max_drawdown: drawdown of cumulative summed returns",
            "max_drawdown_compounded": "peak-to-trough loss of compounded wealth prod(1+r), starting at 1",
        },
        "walk_forward_oos_sharpe": wf_head["oos_sharpe"],
        "walk_forward_oos_span": wf_head["oos_span"],
        "walk_forward": wf,
        "equal_weight_benchmark": {"n_assets": len(ew), "weight_each": 1.0 / len(ew)},
        "weights": {
            "max_sharpe": ms_weights.to_dict(),
            "hrp": hrp_w.to_dict(),
        },
        "article_comparison": article,
    }
    summary_path = RESULTS_DIR / "allocation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    fig_path = plot_weights(ms_weights, hrp_w, FIGURES_DIR / "allocation_weights.png")

    print("quantstack.allocation.compare")
    print(f"  skfolio {skfolio.__version__}, {returns.shape[1]} assets, fit {FIT_START}..{FIT_END}")
    print(
        f"  Max Sharpe: {ms_stats['n_near_zero']}/{ms_stats['n_assets']} near-zero, "
        f"max={ms_stats['max_weight']:.1%}, eff N={ms_stats['effective_n']:.2f}  "
        f"(article: 12/20, 26.6%, 5.3)"
    )
    print(
        f"  HRP:        {hrp_stats['n_near_zero']}/{hrp_stats['n_assets']} near-zero, "
        f"max={hrp_stats['max_weight']:.1%}, eff N={hrp_stats['effective_n']:.2f}  "
        f"(article: 0/20, 10.9%, 15.5)"
    )
    print(
        f"  OOS {TEST_START[:4]}-{TEST_END[:4]} annualized Sharpe: Max Sharpe={ms_oos['annualized_sharpe']:.3f}, "
        f"HRP={hrp_oos['annualized_sharpe']:.3f}  (article: 0.81 / 0.80)"
    )
    print(
        f"  OOS CAGR: Max Sharpe={ms_oos['cagr']:.1%}, HRP={hrp_oos['cagr']:.1%}  "
        f"(arithmetic mean x252: {ms_oos['annualized_mean_arithmetic']:.1%} / {hrp_oos['annualized_mean_arithmetic']:.1%})"
    )
    print(
        f"  OOS max drawdown, compounded: Max Sharpe={ms_oos['max_drawdown_compounded']:.1%}, "
        f"HRP={hrp_oos['max_drawdown_compounded']:.1%}  (uncompounded: "
        f"{ms_oos['max_drawdown_uncompounded']:.1%} / {hrp_oos['max_drawdown_uncompounded']:.1%})"
    )
    print(
        f"  Walk-forward OOS Sharpe (test={WF_TEST_SIZE}/train={WF_TRAIN_SIZE}, reduce_test=True, "
        f"{wf_head['n_folds']} folds, {wf_head['oos_span'][0]}..{wf_head['oos_span'][1]}): "
        f"Max Sharpe={wf_head['oos_sharpe']['max_sharpe']:.3f}, HRP={wf_head['oos_sharpe']['hrp']:.3f}"
    )
    print(
        f"    skfolio default reduce_test=False ({wf_default['n_folds']} folds, "
        f"{wf_default['oos_span'][0]}..{wf_default['oos_span'][1]}, drops the last partial fold): "
        f"Max Sharpe={wf_default['oos_sharpe']['max_sharpe']:.3f}, HRP={wf_default['oos_sharpe']['hrp']:.3f}"
    )
    print(
        f"  Article match at printed precision: {article['all_match_at_printed_precision']}; "
        f"qualitative story holds: {article['qualitative_story_holds']}"
    )
    print(f"  wrote {_display_path(weights_csv)}")
    print(f"  wrote {_display_path(summary_path)}")
    print(f"  wrote {_display_path(fig_path)}")
    print(f"  main() runtime: {time.perf_counter() - t0:.2f}s (excludes ~3 s of imports)")

    return summary


if __name__ == "__main__":
    main()
