"""The thesis price panel: GBP total-return daily levels in, one engine-ready window out.

Input (``prices_gbp_daily.csv`` at the repository root, from the user's thesis
build): one row per trading day (2526 rows, 2016-09-16..2026-09-16), one column
per instrument (84: the 54 holdings, the wider universe, benchmarks, proxies).
The values are a GBP **total-return index** -- dividends reinvested on the
ex-date, FX already applied -- not share prices: BRK-B's level is ~26,000,
LTBR's ~0.001.  The first header cell is empty (the date column is the unnamed
index), which :func:`load_panel` handles explicitly; :func:`verify_panel_file`
checks the file against the build's ``_price_panel_manifest.json``.

The window policy (:func:`select_window`)
-----------------------------------------
The window is ``[start, end]`` -- the repo's convention (see
``execution/backtest.py``): the strategy spends its first ``lookback_bars``
bars warming up and trades from then on.  A ticker is *excluded*, with the
reason recorded, when

* ``not_in_panel``       -- no such column;
* ``no_data``            -- no level at all up to ``end``;
* ``listed_after_start`` -- its first level is after the window's first bar;
* ``excluded_by_user``   -- named in ``exclude`` (a sensitivity run,
  ``--exclude``); no other check is made for it.

Missing levels inside a ticker's own span are forward-filled for runs of at
most ``max_ffill_gap`` bars (default 3, the thesis build's own "<= 3-day
forward-fill" rule in ``fetch_log.json``; in the real panel this fills only
DBMG.L on 2025-04-22/23).  Nothing is ever back-filled.  A longer run -- inside
the span or a stale tail before ``end`` -- raises ``ValueError`` by default
(``gap_policy="raise"``); ``gap_policy="exclude"`` drops the ticker instead,
with the reason ``interior_gap`` or ``stale_at_end``.  With
``strict_calendar=True`` nothing is filled: only the days on which every
selected ticker has an observed level are kept.

Rescaling for the engine (:func:`rescale_for_engine`, on by default)
--------------------------------------------------------------------
The engine trades whole shares, and each instrument's tick comes from its
own data (``execution/data.py``: 0.01 when every close is >= 1, finer below).
At BRK-B's 26,000 a small line buys no shares, and at LTBR's 0.0008 a level
needs a tick of 1e-7.  Returns are invariant to a per-column constant, so each
column is multiplied by ``floor / min(column over the window)``: every name's
*minimum* in the window becomes 100.00 (every instrument then gets the 0.01
tick, at most 0.005% of a level), then rounded to 6 decimals.  Peaking at 100
instead would not do: EDIT's trough would sit at 1.54.  The largest rescaled
level is 100 x the column's max/min range (EDIT ~8,700), which is why the
thesis runner trades a GBP 100,000,000 book and scales the curves back to the
GBP 200,000 thesis book (``run.py``).
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

#: Fewer surviving names than this is not a portfolio worth backtesting
#: (HRP's bisection needs 3, see ``allocation.weights.MIN_HRP_ASSETS``).
MIN_TICKERS = 3
#: Longest run of missing levels that is forward-filled (the build's own rule).
DEFAULT_MAX_FFILL_GAP = 3
#: Every rescaled column's minimum over the window.
DEFAULT_RESCALE_FLOOR = 100.0
#: Rescaled levels are rounded to this many decimals.
RESCALE_DECIMALS = 6
#: The build's manifest of panel checksums, next to the panel.
MANIFEST_NAME = "_price_panel_manifest.json"

GAP_POLICIES: tuple[str, ...] = ("raise", "exclude")
EXCLUSION_REASONS: tuple[str, ...] = (
    "not_in_panel", "no_data", "listed_after_start", "interior_gap", "stale_at_end", "excluded_by_user",
)
EXCLUSION_COLUMNS: tuple[str, ...] = (
    "ticker", "reason", "detail", "first_valid", "last_valid", "weight_total",
)


def load_panel(path: str | Path) -> pd.DataFrame:
    """Read a wide price CSV whose first column is the (possibly unnamed) date index.

    Returns a float DataFrame indexed by a tz-naive ``DatetimeIndex`` named
    ``date``, sorted ascending, one column per header cell (stripped).
    ``ValueError`` for: a missing file, duplicate column names (pandas would
    silently rename the second ``X`` to ``X.1``, which for dotted tickers such
    as ``AZN.L`` looks like another ticker), dates that are not ISO-8601 or
    carry a time of day, duplicate dates, non-numeric values, or no rows.
    """
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"price panel not found: {path}")
    with path.open(newline="") as fh:
        header = next(csv.reader(fh), None)
    if not header or len(header) < 2:
        raise ValueError(f"{path}: expected a date column and at least one price column")
    columns = [c.strip() for c in header[1:]]
    dups = sorted({c for c in columns if columns.count(c) > 1})
    if dups:
        raise ValueError(f"{path}: duplicate column(s) {dups}")
    df = pd.read_csv(path, index_col=0, dtype={0: str})
    df.columns = columns
    if df.empty:
        raise ValueError(f"{path}: no rows")
    try:
        idx = pd.DatetimeIndex(pd.to_datetime(df.index.astype(str).str.strip(), format="ISO8601"))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{path}: the first column must hold ISO dates (YYYY-MM-DD): {exc}") from None
    if idx.tz is not None:
        idx = idx.tz_convert(None)
    if not (idx == idx.normalize()).all():
        raise ValueError(f"{path}: dates carry a time of day; expected one row per trading day")
    df.index = idx.rename("date")
    df = df.sort_index(kind="stable")
    dup_dates = df.index[df.index.duplicated()].unique()
    if len(dup_dates):
        raise ValueError(f"{path}: duplicate date(s) {[d.date().isoformat() for d in dup_dates[:5]]}")
    bad = []
    for c in df.columns:
        try:
            df[c] = df[c].astype(float)
        except (ValueError, TypeError):
            bad.append(c)
    if bad:
        raise ValueError(f"{path}: non-numeric values in column(s) {bad}")
    assert df.index.is_monotonic_increasing and df.index.is_unique
    return df


def sha256_of(path: str | Path) -> str:
    """Hex sha256 of a file's bytes."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify_panel_file(
    path: str | Path, panel: pd.DataFrame, expected_shape: tuple[int, int] | None = None
) -> dict:
    """Check the panel file against the build's manifest (and, optionally, its shape).

    The manifest is ``_price_panel_manifest.json`` next to the file, mapping a
    file name to ``{"repaired_sha256": ..., "as_of": ...}``.  A manifest entry
    whose checksum differs from the file raises ``ValueError`` (the file is
    not the one the build verified); a missing manifest or entry is only a
    warning.  ``expected_shape`` (rows, columns) raises on mismatch.  Returns
    what was checked, for the summary.
    """
    path = Path(path)
    out: dict = {"file": path.name, "sha256": sha256_of(path), "shape": list(panel.shape),
                 "manifest": None, "manifest_sha256": None, "as_of": None, "manifest_match": None,
                 "warning": None}
    if expected_shape is not None and tuple(panel.shape) != tuple(expected_shape):
        raise ValueError(f"{path.name}: expected shape {tuple(expected_shape)}, got {panel.shape}")
    manifest = path.parent / MANIFEST_NAME
    if not manifest.is_file():
        out["warning"] = f"no {MANIFEST_NAME} next to {path.name}: checksum not verified"
        return out
    try:
        entry = json.loads(manifest.read_text()).get(path.name)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"{manifest}: not a JSON object of file entries ({exc})") from None
    out["manifest"] = manifest.name
    if not isinstance(entry, Mapping) or "repaired_sha256" not in entry:
        out["warning"] = f"{MANIFEST_NAME} has no checksum for {path.name}: not verified"
        return out
    out.update(manifest_sha256=entry["repaired_sha256"], as_of=entry.get("as_of"),
               manifest_match=entry["repaired_sha256"] == out["sha256"])
    if not out["manifest_match"]:
        raise ValueError(f"{path.name}: sha256 {out['sha256'][:12]}... does not match {MANIFEST_NAME} "
                         f"({str(entry['repaired_sha256'])[:12]}...): not the panel the build verified")
    return out


def _nan_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """``[(first_row, length), ...]`` of the runs of True in a boolean array."""
    if not mask.any():
        return []
    padded = np.concatenate(([False], mask, [False])).astype(np.int8)
    edges = np.diff(padded)
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    return [(int(s), int(e - s)) for s, e in zip(starts, ends)]


def availability(panel: pd.DataFrame, tickers: Iterable[str]) -> pd.DataFrame:
    """Per-ticker data coverage over the whole panel, indexed by ``ticker`` (input order).

    Columns: ``in_panel``, ``first_valid``, ``last_valid`` (Timestamps, NaT
    when there is no level), ``n_valid``, ``interior_nans`` (missing levels
    between the first and last valid one), ``longest_interior_gap`` (bars),
    ``max_abs_daily_return`` (largest ``|level_t / level_prev - 1|`` between
    consecutive *observed* levels -- a data-quality flag: an unadjusted share
    consolidation or a 100x quote-scale glitch shows up here) and
    ``max_abs_return_date``.  A ticker missing from the panel gets a row with
    ``in_panel=False`` rather than an error.
    """
    rows = []
    for t in tickers:
        t = str(t)
        row = {"ticker": t, "in_panel": t in panel.columns, "first_valid": pd.NaT,
               "last_valid": pd.NaT, "n_valid": 0, "interior_nans": 0,
               "longest_interior_gap": 0, "max_abs_daily_return": float("nan"),
               "max_abs_return_date": pd.NaT}
        if row["in_panel"]:
            s = panel[t]
            fv, lv = s.first_valid_index(), s.last_valid_index()
            if fv is not None:
                inner = s.loc[fv:lv].isna().to_numpy()
                runs = _nan_runs(inner)
                rets = s.dropna().pct_change().abs().dropna()
                row.update(first_valid=fv, last_valid=lv, n_valid=int(s.notna().sum()),
                           interior_nans=int(inner.sum()),
                           longest_interior_gap=max((n for _, n in runs), default=0))
                if not rets.empty:
                    row.update(max_abs_daily_return=float(rets.max()),
                               max_abs_return_date=rets.idxmax())
        rows.append(row)
    return pd.DataFrame(rows).set_index("ticker")


def _exclusion_reasons(
    s: pd.Series, window: pd.DatetimeIndex, max_ffill_gap: int
) -> list[tuple[str, str]]:
    """``[(code, detail), ...]`` for one ticker's column ``s`` (panel rows up to ``end``)."""
    fv, lv = s.first_valid_index(), s.last_valid_index()
    if fv is None:
        return [("no_data", "no level on or before the window's last bar")]
    w0, w1 = window[0], window[-1]
    out: list[tuple[str, str]] = []
    if fv > w0:
        out.append(("listed_after_start",
                    f"first level {fv.date()} is after the window's first bar {w0.date()}"))
    seg = s.loc[fv:]  # first level .. window end: leading NaNs are not gaps
    mask = seg.isna().to_numpy()
    idx = seg.index
    for first, n in _nan_runs(mask):
        last_row = first + n - 1
        if idx[last_row] < w0:  # the gap ended before the window: irrelevant
            continue
        if last_row == len(seg) - 1:
            if n > max_ffill_gap:
                out.append(("stale_at_end", f"last level {lv.date()}: {n} bars missing up to "
                                            f"{w1.date()} (> max_ffill_gap={max_ffill_gap})"))
        elif n > max_ffill_gap:
            out.append(("interior_gap", f"{n} missing bars {idx[first].date()}..{idx[last_row].date()} "
                                        f"(> max_ffill_gap={max_ffill_gap})"))
    return out


def select_window(
    panel: pd.DataFrame,
    tickers: Sequence[str],
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    lookback_bars: int,
    max_ffill_gap: int = DEFAULT_MAX_FFILL_GAP,
    strict_calendar: bool = False,
    weights: Mapping[str, float] | None = None,
    gap_policy: str = "raise",
    exclude: Iterable[str] = (),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The engine-ready window and the table of excluded tickers (policy: module docstring).

    Returns ``(prices, exclusions)``.  ``prices`` is indexed by date over
    ``[start, end]``, one float column per surviving ticker in the order of
    ``tickers``, with no NaN and an all-valid first row.  ``exclusions`` has
    the columns :data:`EXCLUSION_COLUMNS` (``reason`` holds ``;``-joined codes
    from :data:`EXCLUSION_REASONS`, ``detail`` says why in words,
    ``weight_total`` comes from ``weights`` when given).  Tickers in
    ``exclude`` are dropped with the reason ``excluded_by_user``.

    Raises ``ValueError`` for duplicate tickers, ``start > end``, an empty
    window, ``max_ffill_gap < 0``, an unknown ``gap_policy``, a gap longer
    than ``max_ffill_gap`` (with ``gap_policy="raise"``), a non-positive or
    infinite level among the survivors, fewer than :data:`MIN_TICKERS`
    survivors, or a window the engine cannot trade
    (``execution.backtest.check_window``: more than ``lookback_bars`` bars).
    """
    from quantstack.execution.backtest import check_window

    tickers = [str(t) for t in tickers]
    dups = sorted({t for t in tickers if tickers.count(t) > 1})
    if dups:
        raise ValueError(f"duplicate tickers: {dups}")
    if max_ffill_gap < 0:
        raise ValueError(f"max_ffill_gap must be >= 0, got {max_ffill_gap}")
    if gap_policy not in GAP_POLICIES:
        raise ValueError(f"gap_policy must be one of {GAP_POLICIES}, got {gap_policy!r}")
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if start > end:
        raise ValueError(f"start {start.date()} is after end {end.date()}")
    window = panel.loc[start:end].index
    if window.empty:
        raise ValueError(f"the panel has no rows in {start.date()}..{end.date()} "
                         f"(it covers {panel.index[0].date()}..{panel.index[-1].date()})")
    upto_end = panel.loc[:end]

    included: list[str] = []
    excluded: list[dict] = []
    gaps: dict[str, str] = {}
    exclude = {str(t) for t in exclude}
    for t in tickers:
        if t in exclude:
            reasons = [("excluded_by_user", "excluded by user")]
        elif t not in panel.columns:
            reasons = [("not_in_panel", "no such column in the price panel")]
        else:
            reasons = _exclusion_reasons(upto_end[t], window, max_ffill_gap)
        if gap_policy == "raise" and not any(code == "listed_after_start" for code, _ in reasons):
            for code, detail in reasons:
                if code in ("interior_gap", "stale_at_end"):
                    gaps[t] = detail
        if not reasons:
            included.append(t)
            continue
        s = panel[t] if t in panel.columns else pd.Series(dtype=float)
        excluded.append({
            "ticker": t,
            "reason": ";".join(code for code, _ in reasons),
            "detail": "; ".join(detail for _, detail in reasons),
            "first_valid": s.first_valid_index() if not s.empty else pd.NaT,
            "last_valid": s.last_valid_index() if not s.empty else pd.NaT,
            "weight_total": float(weights[t]) if weights is not None and t in weights else float("nan"),
        })
    if gaps:
        raise ValueError(f"gaps longer than max_ffill_gap={max_ffill_gap} bars (never back-filled; "
                         f"pass gap_policy='exclude' to drop these names instead): {gaps}")
    exclusions = pd.DataFrame(excluded, columns=list(EXCLUSION_COLUMNS))

    if len(included) < MIN_TICKERS:
        raise ValueError(f"only {len(included)} of {len(tickers)} tickers have usable prices in "
                         f"{start.date()}..{end.date()} (need {MIN_TICKERS}); excluded: "
                         f"{dict(zip(exclusions['ticker'], exclusions['reason']))}")
    raw = panel.loc[start:end, included]
    if strict_calendar:
        prices = raw.loc[raw.notna().all(axis=1)]
    else:
        # fill from the rows before the window too, so a holiday on the first bar is carried in
        prices = upto_end[included].ffill(limit=max_ffill_gap).loc[start:end]
    prices = prices.astype(float)
    missing = prices.isna().sum()
    if missing.any():  # cannot happen after the checks above; a safety net that names the cells
        raise ValueError(f"missing levels after the fill: {missing[missing > 0].to_dict()}")
    if prices.empty or prices.iloc[0].isna().any():
        raise ValueError(f"the window's first row is not all-valid in {start.date()}..{end.date()}")
    values = prices.to_numpy()
    bad = [c for c, ok in zip(prices.columns, (np.isfinite(values) & (values > 0)).all(axis=0)) if not ok]
    if bad:
        raise ValueError(f"non-positive or infinite levels for {bad} in {start.date()}..{end.date()}; "
                         "a total-return level must be > 0 (fix the data or drop the ticker)")
    check_window(prices, lookback_bars)
    return prices, exclusions


def filled_cells(panel: pd.DataFrame, prices: pd.DataFrame) -> dict[str, int]:
    """Per ticker, how many levels of ``prices`` were forward-filled (missing in ``panel``)."""
    raw = panel.loc[prices.index, list(prices.columns)]
    return {str(c): int(n) for c, n in raw.isna().sum().items()}


def rescale_for_engine(
    prices: pd.DataFrame, floor: float = DEFAULT_RESCALE_FLOOR, decimals: int = RESCALE_DECIMALS
) -> tuple[pd.DataFrame, pd.Series, dict]:
    """Scale each column so its minimum over the window is ``floor``; return ``(rescaled, factors, check)``.

    ``rescaled[c] = round(prices[c] * factors[c], decimals)`` with
    ``factors[c] = floor / prices[c].min()``.  Why: module docstring.  The
    day-over-day returns of the unrounded rescale must equal the input's to
    within 1e-12 (``RuntimeError`` otherwise); ``check`` reports that
    difference and the one after rounding (at most ~1e-8 with ``floor`` 100
    and 6 decimals: a level of 100 rounded to 1e-6 moves by 1e-8 relative).
    ``ValueError`` for a non-positive ``floor`` or a non-positive level.
    """
    if not floor > 0:
        raise ValueError(f"floor must be > 0, got {floor}")
    lows = prices.min()
    if not (lows > 0).all():
        raise ValueError(f"non-positive levels cannot be rescaled: {lows[~(lows > 0)].to_dict()}")
    factors = (floor / lows).astype(float)
    exact = prices * factors
    before = prices.pct_change().iloc[1:].to_numpy()
    diff_exact = float(np.nanmax(np.abs(exact.pct_change().iloc[1:].to_numpy() - before), initial=0.0))
    if not diff_exact < 1e-12:
        raise RuntimeError(f"rescaling changed daily returns by {diff_exact:.3g} (> 1e-12)")
    rescaled = exact.round(decimals)
    diff_rounded = float(np.nanmax(np.abs(rescaled.pct_change().iloc[1:].to_numpy() - before), initial=0.0))
    return rescaled, factors, {"floor": floor, "decimals": decimals,
                               "max_abs_return_diff_unrounded": diff_exact,
                               "max_abs_return_diff_after_rounding": diff_rounded}


def engine_price_diagnostics(prices: pd.DataFrame) -> pd.DataFrame:
    """Per ticker: window ``range_ratio`` (max/min) and ``engine_min`` / ``engine_max``
    (the levels the engine sees; its tick comes from each instrument's own
    data, see ``execution/data.py``)."""
    lo, hi = prices.min(), prices.max()
    return pd.DataFrame({"range_ratio": hi / lo, "engine_min": lo, "engine_max": hi}).rename_axis("ticker")


__all__ = [
    "DEFAULT_MAX_FFILL_GAP",
    "DEFAULT_RESCALE_FLOOR",
    "EXCLUSION_COLUMNS",
    "EXCLUSION_REASONS",
    "GAP_POLICIES",
    "MANIFEST_NAME",
    "MIN_TICKERS",
    "RESCALE_DECIMALS",
    "availability",
    "engine_price_diagnostics",
    "filled_cells",
    "load_panel",
    "rescale_for_engine",
    "select_window",
    "sha256_of",
    "verify_panel_file",
]
