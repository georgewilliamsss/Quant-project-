"""The thesis book: ``data/thesis/thesis_holdings.csv`` in, tickers / sleeves / weights out.

The holdings file is the user's own two-sleeve portfolio (see
``data/thesis/README.md``): 14 ``core`` lines (mean-variance optimised, ~80%
of the GBP 200,000 book) and 40 equal-weighted ``moonshot`` lines (0.5% of the
book each).  ``weight_total`` is each line's fraction of the whole book.

Everything here is pure pandas: load and validate the file, read the weights
and sleeves off it, and renormalise the weights over whichever tickers survive
the price-data checks (:func:`renormalise`, :func:`sleeve_split`).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from pathlib import Path

import pandas as pd

#: Columns :func:`load_holdings` requires (the file has more; they are kept).
REQUIRED_COLUMNS: tuple[str, ...] = ("ticker", "name", "sleeve", "weight_total")
#: The two sleeves of the thesis book.
SLEEVES: tuple[str, ...] = ("core", "moonshot")
#: 14 core + 40 moonshot lines in the thesis as uploaded.
EXPECTED_HOLDINGS = 54


def load_holdings(path: str | Path, expected_n: int | None = EXPECTED_HOLDINGS) -> pd.DataFrame:
    """Read and validate the holdings CSV; return it with a clean ``ticker`` column.

    Checks (``ValueError`` naming the problem): the :data:`REQUIRED_COLUMNS`
    exist; tickers are non-empty and unique after stripping whitespace;
    ``expected_n`` rows when it is not ``None``; every ``sleeve`` is one of
    :data:`SLEEVES`; every ``weight_total`` is a finite number >= 0 and their
    sum is positive.  Row order is kept (it is the thesis's own order).
    """
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"holdings file not found: {path}")
    df = pd.read_csv(path, dtype={"ticker": str, "sleeve": str})
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing column(s) {missing}; have {list(df.columns)}")
    df = df.copy()
    df["ticker"] = df["ticker"].fillna("").astype(str).str.strip()
    if (df["ticker"] == "").any():
        rows = [int(i) + 2 for i in df.index[df["ticker"] == ""]]  # 1-based, after the header
        raise ValueError(f"{path}: empty ticker on line(s) {rows}")
    dups = sorted(df["ticker"][df["ticker"].duplicated()].unique())
    if dups:
        raise ValueError(f"{path}: duplicate ticker(s) {dups}")
    if expected_n is not None and len(df) != expected_n:
        raise ValueError(f"{path}: expected {expected_n} holdings, found {len(df)}")
    df["sleeve"] = df["sleeve"].fillna("").astype(str).str.strip().str.lower()
    bad_sleeve = df.loc[~df["sleeve"].isin(SLEEVES), ["ticker", "sleeve"]]
    if not bad_sleeve.empty:
        raise ValueError(f"{path}: sleeve must be one of {SLEEVES}; got "
                         f"{dict(zip(bad_sleeve['ticker'], bad_sleeve['sleeve']))}")
    weights = pd.to_numeric(df["weight_total"], errors="coerce")
    bad_w = df.loc[~(weights.apply(lambda w: math.isfinite(w) and w >= 0)), "ticker"].tolist()
    if bad_w:
        raise ValueError(f"{path}: weight_total must be a finite number >= 0 for {bad_w}")
    if not weights.sum() > 0:
        raise ValueError(f"{path}: weight_total sums to {weights.sum()}; need a positive total")
    df["weight_total"] = weights.astype(float)
    return df.reset_index(drop=True)


def thesis_weights(holdings: pd.DataFrame) -> dict[str, float]:
    """``{ticker: weight_total}`` in file order (fractions of the whole book, not rescaled)."""
    return {str(t): float(w) for t, w in zip(holdings["ticker"], holdings["weight_total"])}


def sleeve_of(holdings: pd.DataFrame) -> dict[str, str]:
    """``{ticker: sleeve}`` in file order."""
    return {str(t): str(s) for t, s in zip(holdings["ticker"], holdings["sleeve"])}


def renormalise(weights: Mapping[str, float], tickers: Iterable[str]) -> dict[str, float]:
    """``weights`` restricted to ``tickers`` and rescaled to sum to 1 (order of ``tickers``).

    This is how the thesis weights of excluded names are redistributed: pro
    rata over the names that remain, so the *relative* weights of the
    survivors are exactly the thesis's.  Raises ``ValueError`` if a ticker has
    no weight or the restricted weights sum to zero.
    """
    tickers = [str(t) for t in tickers]
    missing = [t for t in tickers if t not in weights]
    if missing:
        raise ValueError(f"no thesis weight for {missing}")
    total = sum(float(weights[t]) for t in tickers)
    if not total > 0:
        raise ValueError(f"thesis weights over {tickers} sum to {total}; nothing to hold")
    return {t: float(weights[t]) / total for t in tickers}


def renormalise_within_sleeves(
    weights: Mapping[str, float], tickers: Iterable[str], sleeves: Mapping[str, str],
    split: Mapping[str, float],
) -> dict[str, float]:
    """``weights`` over ``tickers``, rescaled *within* each sleeve so the sleeves sum to ``split``.

    The ``own_weights_8020`` scheme: when names are excluded, :func:`renormalise`
    spreads their weight over everyone, which shifts the core/moonshot split
    (excluding 18 moonshots turns 80/20 into ~88/12).  Here each sleeve keeps
    its thesis share (``split``, normalised to sum to 1) and its surviving
    names share it in their thesis proportions.  ``ValueError`` if a sleeve
    with a positive share has no surviving name with a positive weight.
    """
    tickers = [str(t) for t in tickers]
    total_split = sum(float(v) for v in split.values())
    if not total_split > 0:
        raise ValueError(f"sleeve split {dict(split)} sums to {total_split}")
    by_sleeve: dict[str, float] = {}
    for t in tickers:
        if t not in weights:
            raise ValueError(f"no thesis weight for {t}")
        by_sleeve[sleeves[t]] = by_sleeve.get(sleeves[t], 0.0) + float(weights[t])
    empty = [s for s, share in split.items() if share > 0 and not by_sleeve.get(s, 0.0) > 0]
    if empty:
        raise ValueError(f"sleeve(s) {empty} have no included name to carry their "
                         f"{', '.join(f'{split[s]:.1%}' for s in empty)} share")
    return {t: float(weights[t]) / by_sleeve[sleeves[t]] * float(split.get(sleeves[t], 0.0)) / total_split
            for t in tickers}


def sleeve_split(weights: Mapping[str, float], sleeves: Mapping[str, str]) -> dict[str, float]:
    """Total weight per sleeve (every sleeve in :data:`SLEEVES`, 0.0 when empty)."""
    out = dict.fromkeys(SLEEVES, 0.0)
    for t, w in weights.items():
        out[sleeves[t]] += float(w)
    return out


__all__ = [
    "EXPECTED_HOLDINGS",
    "REQUIRED_COLUMNS",
    "SLEEVES",
    "load_holdings",
    "renormalise",
    "renormalise_within_sleeves",
    "sleeve_of",
    "sleeve_split",
    "thesis_weights",
]
