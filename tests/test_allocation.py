"""Tests for quantstack.allocation (compare.py and weights.py).

Fitting both allocators on the real skfolio in-sample window (2015-2019, 1258
rows x 20 assets) takes well under a second, so we do it once per module in a
fixture rather than mocking skfolio out. Part of the point of these tests is
to catch a skfolio API or behaviour change, which a mock would hide. That is
also why the article's numbers are pinned below.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from skfolio import Portfolio

from quantstack import contracts as c
from quantstack.allocation import compare, weights


@pytest.fixture(scope="module")
def returns():
    return compare.load_returns()


@pytest.fixture(scope="module")
def fit_returns(returns):
    fit, _test = compare.fit_test_split(returns)
    return fit


@pytest.fixture(scope="module")
def ms_weights(fit_returns):
    return c.fit_weights(compare.build_max_sharpe(), fit_returns)


@pytest.fixture(scope="module")
def hrp_w(fit_returns):
    return c.fit_weights(compare.build_hrp(), fit_returns)


@pytest.fixture(scope="module")
def fixed(returns):
    return compare.fixed_split_comparison(returns)


def test_max_sharpe_weights_validate(ms_weights):
    # fit_weights already ran validate_weights internally; re-check explicitly
    # so this test still catches a regression if that wiring ever changes.
    clean = c.validate_weights(ms_weights)
    assert set(clean) == set(ms_weights)
    assert sum(clean.values()) <= 1.0 + 1e-6


def test_hrp_weights_validate(hrp_w):
    clean = c.validate_weights(hrp_w)
    assert set(clean) == set(hrp_w)
    assert sum(clean.values()) <= 1.0 + 1e-6


def test_hrp_holds_all_names_with_bounded_max_weight(hrp_w):
    w = np.array(list(hrp_w.values()))
    assert (w > 1e-6).all(), "HRP should not zero out any of the 20 names"
    assert w.max() < 0.2, f"HRP max weight {w.max():.3f} should stay well diversified"


def test_max_sharpe_is_more_concentrated_than_hrp(ms_weights, hrp_w):
    ms_stats = compare.concentration_stats(pd.Series(ms_weights))
    hrp_stats = compare.concentration_stats(pd.Series(hrp_w))
    assert ms_stats["effective_n"] < hrp_stats["effective_n"]
    assert ms_stats["n_near_zero"] > hrp_stats["n_near_zero"]
    assert ms_stats["max_weight"] > hrp_stats["max_weight"]


def test_fixed_split_goes_through_the_contract_adapter(fixed, ms_weights, hrp_w):
    """main()'s pipeline (fixed_split_comparison) must give exactly what
    contracts.fit_weights gives."""
    assert fixed["weights"]["max_sharpe"].to_dict() == pytest.approx(ms_weights, abs=1e-12)
    assert fixed["weights"]["hrp"].to_dict() == pytest.approx(hrp_w, abs=1e-12)


def test_article_numbers_regression(fixed):
    """Pin the numbers this module reproduces. They are identical under the
    skfolio 1.0.2 source and 1.4.0, so drift here means skfolio's behaviour
    changed. Tolerances leave room for solver noise, not for a changed
    story."""
    ins, oos = fixed["in_sample"], fixed["out_of_sample"]
    assert ins["max_sharpe"]["n_near_zero"] == 12
    assert ins["max_sharpe"]["max_weight"] == pytest.approx(0.26599, abs=0.005)
    assert ins["max_sharpe"]["effective_n"] == pytest.approx(5.2555, abs=0.05)
    assert ins["hrp"]["n_near_zero"] == 0
    assert ins["hrp"]["max_weight"] == pytest.approx(0.10885, abs=0.005)
    assert ins["hrp"]["effective_n"] == pytest.approx(15.4526, abs=0.05)
    assert oos["max_sharpe"]["annualized_sharpe"] == pytest.approx(0.80654, abs=0.01)
    assert oos["hrp"]["annualized_sharpe"] == pytest.approx(0.79778, abs=0.01)
    # the article's "similar OOS Sharpe" claim
    assert abs(oos["max_sharpe"]["annualized_sharpe"] - oos["hrp"]["annualized_sharpe"]) < 0.05

    article = compare.article_comparison(ins, oos)
    assert article["all_match_at_printed_precision"], article["matches_article_at_printed_precision"]
    assert article["qualitative_story_holds"] is True


def test_article_verdict_is_computed_not_hard_coded(fixed):
    """Flip the concentration ordering and the verdict must flip with it."""
    ins = {k: dict(v) for k, v in fixed["in_sample"].items()}
    ins["max_sharpe"]["effective_n"] = ins["hrp"]["effective_n"] + 1.0
    verdict = compare.article_comparison(ins, fixed["out_of_sample"])
    assert verdict["qualitative_story_holds"] is False
    assert "does NOT hold" in verdict["note"]


def test_oos_sharpe_matches_hand_computed_definition(fit_returns, returns):
    """Cross-check skfolio's ``annualized_sharpe_ratio`` against the article's
    own definition (mean / std(ddof=1) * sqrt(252) of daily returns). The
    tolerance is tight enough to catch a ddof switch (ddof 0 vs 1 differ by
    about 7e-4 relative here) or a switch to compounded returns."""
    _fit, test_returns = compare.fit_test_split(returns)
    hrp = compare.build_hrp()
    hrp.fit(fit_returns)
    portfolio = hrp.predict(test_returns)

    daily = np.asarray(portfolio.returns, dtype=float)
    hand_sharpe = daily.mean() / daily.std(ddof=1) * np.sqrt(252)

    assert portfolio.annualized_sharpe_ratio == pytest.approx(hand_sharpe, rel=1e-9)


def test_oos_stats_compounded_vs_uncompounded(fixed, returns):
    """annualized_mean_arithmetic is mean*252 (not CAGR); the compounded
    drawdown matches skfolio's own compounded=True Portfolio."""
    _fit, test_returns = compare.fit_test_split(returns)
    for name in ("max_sharpe", "hrp"):
        s = fixed["out_of_sample"][name]
        w = fixed["weights"][name].to_numpy()
        daily = test_returns.to_numpy() @ w
        assert s["annualized_mean_arithmetic"] == pytest.approx(daily.mean() * 252, rel=1e-9)
        wealth = np.prod(1.0 + daily)
        assert s["cagr"] == pytest.approx(wealth ** (252 / len(daily)) - 1.0, rel=1e-9)
        assert s["cagr"] < s["annualized_mean_arithmetic"]
        compounded = Portfolio(X=test_returns, weights=w, compounded=True)
        assert s["max_drawdown_compounded"] == pytest.approx(compounded.max_drawdown, rel=1e-9)
    # the ranking flip that made reporting both drawdowns necessary
    ms, hrp = fixed["out_of_sample"]["max_sharpe"], fixed["out_of_sample"]["hrp"]
    assert ms["max_drawdown_uncompounded"] < hrp["max_drawdown_uncompounded"]
    assert ms["max_drawdown_compounded"] > hrp["max_drawdown_compounded"]


# --------------------------------------------------------------------------
# hrp_weights / equal_weight: the functions other modules import
# --------------------------------------------------------------------------


def _random_returns(n_rows: int, cols, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(rng.normal(0.0004, 0.01, size=(n_rows, len(cols))), columns=list(cols))


def test_hrp_weights_works_on_small_random_returns_frame():
    small = _random_returns(120, "ABCDE")
    w = compare.hrp_weights(small)
    c.validate_weights(w)  # must not raise
    assert set(w) == set("ABCDE")
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-6)


def test_compare_reexports_the_light_module():
    assert compare.hrp_weights is weights.hrp_weights
    assert compare.equal_weight is weights.equal_weight


def test_hrp_weights_two_assets_falls_back_to_inverse_variance():
    """skfolio's HRP crashes on 2 assets. With 2 singleton clusters, HRP's
    bisection *is* inverse-variance weighting, so that is the fallback."""
    small = _random_returns(60, "AB")
    small["B"] *= 2.0  # 4x the variance -> 1/5 of the weight
    w = weights.hrp_weights(small)
    c.validate_weights(w)
    var = small.var(ddof=1)
    expected = (1 / var) / (1 / var).sum()
    assert w == pytest.approx(expected.to_dict(), rel=1e-12)
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-12)


def test_hrp_weights_single_asset_is_rejected():
    """A one-asset frame is a position, not a portfolio: HRP refuses it so a
    caller cannot silently 'allocate' 100% by passing a degenerate universe."""
    import numpy as np
    import pandas as pd

    one = pd.DataFrame({"A": np.random.default_rng(0).normal(size=40)})
    with pytest.raises(ValueError, match="at least 2 assets"):
        compare.hrp_weights(one)


def test_hrp_weights_stringifies_int_labels():
    frame = _random_returns(50, range(4))
    frame.columns = [0, 1, 2, 3]
    assert set(weights.hrp_weights(frame)) == {"0", "1", "2", "3"}


@pytest.mark.parametrize(
    "mutate, match",
    [
        (lambda df: df.iloc[:1], "row"),
        (lambda df: df.assign(B=np.where(np.arange(len(df)) == 3, np.nan, df["B"])), "NaN"),
        (lambda df: df.assign(C=np.inf), "NaN/inf"),
        (lambda df: df.assign(D=0.001), "constant"),
        (lambda df: df.iloc[:, :0], "no asset columns"),
    ],
    ids=["one_row", "nan", "inf", "constant_column", "no_columns"],
)
def test_hrp_weights_rejects_bad_input_with_clear_error(mutate, match):
    with pytest.raises(ValueError, match=match):
        weights.hrp_weights(mutate(_random_returns(40, "ABCD")))


def test_hrp_weights_rejects_duplicate_labels():
    """Two columns literally named "A" must not silently collapse into one
    dict key (and one asset's weight) via ``dict(zip(...))``."""
    frame = _random_returns(40, "ABCD")
    frame.columns = ["A", "A", "C", "D"]
    with pytest.raises(ValueError, match="duplicate"):
        weights.hrp_weights(frame)


def test_hrp_weights_rejects_labels_colliding_after_str():
    """The int 1 and the string "1" are different dict keys until ``str()``
    is applied, at which point they collide -- exactly what every weight
    function here does before returning."""
    frame = _random_returns(40, range(4))
    frame.columns = [1, "1", 2, 3]
    with pytest.raises(ValueError, match="duplicate"):
        weights.hrp_weights(frame)
    # Falls through the same check on the <MIN_HRP_ASSETS closed-form path.
    small = _random_returns(30, range(2))
    small.columns = [1, "1"]
    with pytest.raises(ValueError, match="duplicate"):
        weights.hrp_weights(small)


def test_inverse_variance_weights_rejects_duplicate_labels():
    frame = _random_returns(30, "AB")
    frame.columns = ["A", "A"]
    with pytest.raises(ValueError, match="duplicate"):
        weights.inverse_variance_weights(frame)


def test_hrp_weights_requires_enough_rows_relative_to_asset_count():
    """Below :data:`weights.MIN_HRP_ROWS_PER_ASSET` x n_assets rows, HRP's
    sample covariance is too noisy to trust, even though it clears the
    generic ``check_returns`` floor of 2 rows."""
    n_assets = 5
    min_rows = weights.MIN_HRP_ROWS_PER_ASSET * n_assets
    too_few = _random_returns(min_rows - 1, "ABCDE")
    with pytest.raises(ValueError, match=f"at least {min_rows} rows"):
        weights.hrp_weights(too_few)
    # One row more clears the floor and fits normally.
    enough = _random_returns(min_rows, "ABCDE")
    w = weights.hrp_weights(enough)
    c.validate_weights(w)
    assert set(w) == set("ABCDE")


def test_equal_weight_sums_to_one_and_is_uniform():
    small = _random_returns(60, "WXYZ", seed=1)
    w = compare.equal_weight(small)
    c.validate_weights(w)
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-9)
    assert all(v == pytest.approx(0.25) for v in w.values())


def test_equal_weight_depends_only_on_columns():
    nan_frame = pd.DataFrame(np.nan, index=range(5), columns=list("ABC"))
    empty_frame = pd.DataFrame(columns=list("ABC"), dtype=float)
    for frame in (nan_frame, empty_frame):
        w = weights.equal_weight(frame)
        assert w == pytest.approx({"A": 1 / 3, "B": 1 / 3, "C": 1 / 3})
    with pytest.raises(ValueError):
        weights.equal_weight(pd.DataFrame())


def test_equal_weight_rejects_duplicate_labels():
    """Without this check, ``{c: 1.0 / n for c in columns}`` would collapse
    the two "A" columns into one key still worth 1/n, so the mapping would
    sum to 3/4 instead of 1 and validate_weights would accept it (<= 1)."""
    frame = pd.DataFrame(np.nan, index=range(5), columns=["A", "A", "B", "C"])
    with pytest.raises(ValueError, match="duplicate"):
        weights.equal_weight(frame)


def test_equal_weight_rejects_labels_colliding_after_str():
    frame = pd.DataFrame(np.nan, index=range(5), columns=[1, "1", 2])
    with pytest.raises(ValueError, match="duplicate"):
        weights.equal_weight(frame)


def test_importing_weights_does_not_touch_matplotlib():
    """Importing the allocators must not switch the global matplotlib backend.
    Run in a fresh interpreter because this test process may already have
    matplotlib loaded.

    The subprocess must not depend on the caller's cwd or on quantstack
    already being importable from it (quantstack is not pip-installed; it is
    only importable via ``python -m`` from the repo root, or with the repo
    root on ``PYTHONPATH``). Both are set explicitly here so this test passes
    regardless of where pytest itself was invoked from.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    code = (
        "import sys; import quantstack.allocation.weights, quantstack.allocation.compare; "
        "print('matplotlib' in sys.modules)"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root)
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=repo_root,
        env=env,
    )
    assert out.stdout.strip() == "False"


# --------------------------------------------------------------------------
# Walk-forward and the CLI
# --------------------------------------------------------------------------


@pytest.mark.slow
def test_walk_forward_oos_sharpe_runs(returns):
    """The sklearn-contract demonstration (cross_val_predict + WalkForward).
    Marked slow because it refits both allocators several times; it still
    runs in about a second, but it repeats work test_main_writes_expected_files
    already covers."""
    window = returns.loc[compare.FIT_START : compare.TEST_END]
    result = compare.walk_forward_oos_sharpe(window)
    assert set(result) == {"max_sharpe", "hrp"}
    assert all(np.isfinite(v) for v in result.values())


def test_main_writes_expected_files(tmp_path, monkeypatch):
    """Smoke-test the CLI entry point end to end, redirected into tmp_path so
    it does not depend on (or clobber) the real results/ directory."""
    monkeypatch.setattr(compare, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(compare, "FIGURES_DIR", tmp_path / "figures")

    summary = compare.main()

    assert (tmp_path / "allocation_weights.csv").exists()
    assert (tmp_path / "allocation_summary.json").exists()
    assert (tmp_path / "figures" / "allocation_weights.png").exists()
    assert summary["in_sample"]["hrp"]["n_near_zero"] == 0
    assert summary["in_sample"]["max_sharpe"]["n_near_zero"] > summary["in_sample"]["hrp"]["n_near_zero"]

    # The walk-forward block must report the span it actually scored.
    wf = summary["walk_forward"]
    full = wf["variants"]["reduce_test_true"]
    default = wf["variants"]["reduce_test_false_default"]
    assert full["oos_span"][1] == wf["input_span"][1] == "2022-12-28"
    assert (full["n_folds"], full["n_oos_days"]) == (5, 1256)
    assert default["oos_span"] == ["2018-01-03", "2022-01-03"]
    assert (default["n_folds"], default["n_oos_days"]) == (4, 1008)
    assert summary["walk_forward_oos_sharpe"] == full["oos_sharpe"]
    assert full["oos_sharpe"]["max_sharpe"] == pytest.approx(0.861, abs=0.01)
    assert full["oos_sharpe"]["hrp"] == pytest.approx(0.777, abs=0.01)

    # Deterministic output: a second run writes a byte-identical summary.
    first = (tmp_path / "allocation_summary.json").read_text()
    compare.main()
    assert (tmp_path / "allocation_summary.json").read_text() == first
    assert "runtime" not in json.loads(first)



def test_fixed_split_comparison_rejects_duplicate_labels():
    import numpy as np
    import pandas as pd
    import pytest as _pytest

    from quantstack.allocation.compare import fixed_split_comparison

    idx = pd.bdate_range("2015-01-01", periods=60)
    dup = pd.DataFrame(np.random.default_rng(1).normal(size=(60, 3)), index=idx, columns=["A", "A", "B"])
    with _pytest.raises(ValueError):
        fixed_split_comparison(dup)
