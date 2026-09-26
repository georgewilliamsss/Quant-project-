"""Reusable allocators: returns frame in, validated ``Weights`` out.

This is the import-light half of ``quantstack.allocation``. The execution
module (NautilusTrader event loop, trailing window) and the dashboard can
import from here without pulling in matplotlib, the bundled datasets or the
model-selection machinery that the article comparison in
:mod:`quantstack.allocation.compare` needs. ``compare`` re-exports every name
defined here, so ``from quantstack.allocation.compare import hrp_weights``
keeps working.

Import note (checked, not assumed): ``ObjectiveFunction`` comes from
``skfolio.optimization`` and ``RiskMeasure`` from the top-level ``skfolio``
package. That is true in skfolio 1.4.0 (installed here) and was already true
in 1.0.2 (the article's version, whose top-level ``__init__`` exports only the
measures, ``Population`` and the portfolio classes). No API change was needed
between the two versions for anything in this package.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from skfolio import RiskMeasure
from skfolio.optimization import HierarchicalRiskParity, MeanRisk, ObjectiveFunction

from quantstack.contracts import Weights, fit_weights, validate_weights

#: HRP's recursive bisection needs a real tree to cut. skfolio 1.4.0 fails on
#: 2 assets ("attempt to get argmax of an empty sequence") and on 1 asset
#: ("DataFrame constructor not properly called!"), so below this we use the
#: closed form HRP reduces to (see :func:`hrp_weights`).
MIN_HRP_ASSETS = 3

#: skfolio's covariance sanity check rejects any asset whose sample variance is
#: below this (``NonPositiveVarianceError``); we check first so the caller gets
#: an error that names the problem.
MIN_VARIANCE = 1e-15


def build_max_sharpe() -> MeanRisk:
    """Max Sharpe on the sample covariance: MeanRisk with the default
    EmpiricalPrior (sample mean, sample covariance), long-only and fully
    invested (both are ``MeanRisk`` defaults: ``min_weights=0.0``,
    ``budget=1.0``)."""
    return MeanRisk(
        objective_function=ObjectiveFunction.MAXIMIZE_RATIO,
        risk_measure=RiskMeasure.VARIANCE,
    )


def build_hrp() -> HierarchicalRiskParity:
    """Hierarchical Risk Parity, all defaults (Ward linkage on a
    correlation-distance matrix, recursive bisection by inverse-variance)."""
    return HierarchicalRiskParity()


def check_returns(returns: pd.DataFrame, min_rows: int = 2) -> None:
    """Raise ``ValueError`` with a readable message if ``returns`` cannot be
    handed to a covariance-based allocator.

    Preconditions: a DataFrame with at least one column, at least ``min_rows``
    rows (a sample covariance with ddof=1 needs 2), no NaN or infinite values,
    and no (near-)constant column (sample variance >= :data:`MIN_VARIANCE`).
    Without this check, each failure shows up as a skfolio or pandas error
    that does not name the cause ("Input X contains NaN", a ddof error,
    ``NonPositiveVarianceError``).
    """
    if not isinstance(returns, pd.DataFrame):
        raise ValueError(f"returns must be a pandas DataFrame, got {type(returns).__name__}")
    if returns.shape[1] == 0:
        raise ValueError("returns has no asset columns")
    if returns.shape[0] < min_rows:
        raise ValueError(
            f"returns has {returns.shape[0]} row(s); at least {min_rows} are needed "
            "to estimate a sample covariance"
        )
    values = returns.to_numpy(dtype=float)
    bad = ~np.isfinite(values).all(axis=0)
    if bad.any():
        cols = [str(c) for c in returns.columns[bad]]
        raise ValueError(
            f"returns contain NaN/inf in column(s) {cols}; drop or fill them before "
            "calling the allocator (it does not guess how)"
        )
    variances = values.var(axis=0, ddof=1)
    flat = variances < MIN_VARIANCE
    if flat.any():
        cols = [str(c) for c in returns.columns[flat]]
        raise ValueError(
            f"column(s) {cols} are (near-)constant over the window (variance < "
            f"{MIN_VARIANCE:g}); a risk-based allocator cannot size them"
        )


def inverse_variance_weights(returns: pd.DataFrame) -> Weights:
    """Weights proportional to 1 / sample variance, normalised to sum to 1."""
    check_returns(returns)
    inv = 1.0 / returns.to_numpy(dtype=float).var(axis=0, ddof=1)
    return validate_weights(dict(zip(returns.columns, inv / inv.sum())))


def hrp_weights(returns: pd.DataFrame) -> Weights:
    """Fit HRP on ``returns`` and return validated target weights.

    This is the function the execution module can import. It calls skfolio
    fresh on a trailing returns window inside the NautilusTrader event loop,
    so it takes nothing but a returns frame and returns nothing but a plain
    ``{symbol: weight}`` mapping. No skfolio object crosses the module
    boundary.

    Preconditions (checked by :func:`check_returns`, which raises
    ``ValueError`` naming the problem): at least 2 rows, no NaN/inf, no
    constant column. Column labels are turned into ``str`` keys.

    Fewer than :data:`MIN_HRP_ASSETS` (3) assets: skfolio's HRP crashes, so we
    return the weights HRP would give. With 2 assets the tree has one split
    between two singleton clusters. The bisection gives the left one
    ``1 - var_l / (var_l + var_r)``, which is exactly inverse-variance
    weighting. With 1 asset the weight is 1.0. Both cases go through
    :func:`inverse_variance_weights`.

    Cost: about 20 ms per call on 20 assets x 20-252 days of real data.
    """
    check_returns(returns)
    if returns.shape[1] < MIN_HRP_ASSETS:
        return inverse_variance_weights(returns)
    return fit_weights(build_hrp(), returns)


def equal_weight(returns: pd.DataFrame) -> Weights:
    """The naive 1/N benchmark.

    It depends only on ``returns.columns``. 1/N uses no estimate, so NaNs, an
    empty index or a constant column do not matter here. Raises ``ValueError``
    only when there are no columns.
    """
    columns = list(returns.columns)
    if not columns:
        raise ValueError("returns has no asset columns")
    n = len(columns)
    return validate_weights({c: 1.0 / n for c in columns})


__all__ = [
    "MIN_HRP_ASSETS",
    "MIN_VARIANCE",
    "build_hrp",
    "build_max_sharpe",
    "check_returns",
    "equal_weight",
    "hrp_weights",
    "inverse_variance_weights",
]
