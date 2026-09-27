"""Documented level repairs to the thesis panel, applied to full series before any slicing.

The thesis build's ``prices_gbp_daily.csv`` is manifest-verified, but it still
carries unadjusted share consolidations: a 1:12 consolidation shows up as a
-91.7% "return" on the day it takes effect.  A returns-driven backtest would
book that as a real loss, and HRP would read it as volatility.  Each repair
here divides every level of one ticker dated *before* a break by a constant,
which moves the whole earlier history onto the post-break scale.  Returns on
every other day are unchanged; the break day's return becomes the true one.

:data:`REPAIRS` is the list, in the order applied.  Each entry says why and how
sure we are (``verified``: ``"confirmed"`` against a primary source from this
sandbox, ``"plausible"`` -- consistent with a public announcement but not
independently confirmed here, or ``"unverified"``).  ``apply_repairs`` logs
every one into the thesis summary with the factor used and the break day's
return before and after; ``--no-repairs`` turns the list off.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

VERIFIED_LEVELS: tuple[str, ...] = ("confirmed", "plausible", "unverified")


@dataclass(frozen=True)
class Repair:
    """Divide ``ticker``'s levels dated before ``date`` by ``divisor``.

    ``divisor=None`` means "the ratio that makes ``date``'s return exactly 0"
    (``level[previous valid day] / level[date]``), for a break whose true
    ratio is unknown.
    """

    ticker: str
    date: str
    divisor: float | None
    reason: str
    verified: str

    def __post_init__(self) -> None:
        if self.verified not in VERIFIED_LEVELS:
            raise ValueError(f"verified must be one of {VERIFIED_LEVELS}, got {self.verified!r}")
        if self.divisor is not None and not self.divisor > 0:
            raise ValueError(f"divisor must be > 0 or None, got {self.divisor}")
        pd.Timestamp(self.date)  # raises on a malformed date


REPAIRS: tuple[Repair, ...] = (
    Repair(
        ticker="MSCL.TO", date="2026-02-02", divisor=12.0,
        reason="1:12 share consolidation (Satellos, announced 2026-01-28, effective about 2026-01-30) "
               "left unadjusted: the panel shows -91.4% on 2026-02-02; after dividing the earlier "
               "levels by 12 the day's return is +3.23%",
        verified="plausible",
    ),
    Repair(
        ticker="MSCL.TO", date="2021-08-19", divisor=None,
        reason="suspected unadjusted consolidation: -95.3% on 2021-08-19 (local 5,472 to 257.8 CAD, "
               "ratio ~21.3) with no confirmed corporate action; neutralised to a 0% return",
        verified="unverified",
    ),
)


def apply_repairs(panel: pd.DataFrame, repairs: Sequence[Repair] = REPAIRS) -> tuple[pd.DataFrame, list[dict]]:
    """Apply ``repairs`` in order to a copy of ``panel``; return ``(repaired, log)``.

    A repair whose ticker is not a column of ``panel`` is skipped and logged
    as such (the panel may already be restricted to a subset of holdings).
    ``ValueError`` if a repair's date is not a row of the panel, or the ticker
    has no level on that date or before it: a repair list that no longer
    matches the data must be looked at, not silently ignored.
    """
    out = panel.copy()
    log: list[dict] = []
    for r in repairs:
        entry = {"ticker": r.ticker, "date": r.date, "reason": r.reason, "verified": r.verified}
        if r.ticker not in out.columns:
            log.append({**entry, "applied": False, "factor": None, "note": "ticker not in the panel"})
            continue
        s = out[r.ticker]
        day = pd.Timestamp(r.date)
        if day not in s.index or pd.isna(s.loc[day]):
            raise ValueError(f"repair {r.ticker} {r.date}: no level on that date")
        before = s.loc[: day - pd.Timedelta(days=1)].dropna()
        if before.empty:
            raise ValueError(f"repair {r.ticker} {r.date}: no level before that date")
        prev_day, prev, cur = before.index[-1], float(before.iloc[-1]), float(s.loc[day])
        factor = float(r.divisor) if r.divisor is not None else prev / cur
        mask = out.index < day
        out.loc[mask, r.ticker] = out.loc[mask, r.ticker] / factor
        log.append({**entry, "applied": True, "factor": factor, "previous_day": prev_day.date().isoformat(),
                    "return_before": cur / prev - 1.0,
                    "return_after": cur / (prev / factor) - 1.0,
                    "levels_divided": int(out.loc[mask, r.ticker].notna().sum())})
    return out, log


__all__ = ["REPAIRS", "VERIFIED_LEVELS", "Repair", "apply_repairs"]
