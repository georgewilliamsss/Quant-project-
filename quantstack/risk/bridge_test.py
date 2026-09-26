"""The bridge test: ORE's bootstrapped curve -> standalone QuantLib -> the same swap.

Why this module exists
----------------------
The article ("Five Repos, One Engine") claims that ORE and QuantLib are one
engine, not two: ORE is QuantLib plus QuantExt plus an XML front-end.  The claim
is checkable.  Take the discount factors ORE bootstrapped for the pricing curve
(the ``curves`` analytic, written by :mod:`quantstack.risk.run_ore` to
``results/risk_curves.csv`` on a 240 x 1M grid), rebuild a curve from them in the
*standalone* QuantLib wheel (``import QuantLib as ql`` - a separate binary from
``import ORE``), rebuild the trade with plain QuantLib instruments, and reprice.
If the two libraries share their calendars, day counters, schedule generator,
coupon pricers and discounting engine, the only thing that can differ is the
curve *between* the numbers we copied across.

Why a single curve is enough: the risk module prices under ORE's ``libor``
market configuration, in which ``Yield/EUR/EUR6M`` is *both* the discount curve
and the EURIBOR-6M forwarding curve (column ``EUR`` == column ``EUR-EURIBOR-6M``
of the report, checked at run time).  One rebuilt handle therefore serves as
``DiscountingSwapEngine`` discount curve *and* ``Euribor6M`` projection curve.
If the risk module is re-run under ``xois_eur`` the two columns differ and this
module builds two handles (OIS discounting, 6M forwarding) automatically.

What we found (QuantLib 1.43 / ORE 1.8.17.0, Example_9 inputs)
---------------------------------------------------------------
* The article's numbers reproduce to the cent: ORE 1,609,885.84 EUR, QuantLib
  rebuild 1,608,800.94 EUR, gap 1,084.89 EUR = 1.08 bp of the 10M notional.
* Payment, accrual and fixing dates of both legs, the 30/360 and A360 accrual
  fractions and the fixed amounts agree exactly with ORE's cashflow report.
* The article attributes the gap to "interpolating between the 240 monthly
  pillars".  The per-cashflow diagnosis says otherwise: **99.5% of it is
  extrapolation, 0.5% is interpolation.**  The curves grid is ``asof + k x 1M``,
  so it ends on 2036-02-05, but the swap's last payment (and the end of its last
  float accrual) is 2036-03-03, 27 days past the grid.  QuantLib extrapolates
  flat-forward from the last monthly segment (continuous A365 forward ~1.55%,
  the 15Y-20Y native segment), while ORE's native curve has a 20Y pillar on
  2036-02-11 after which the forward drops to ~1.32% (20Y-25Y segment); over
  the 27 days the average forward is 1.55% vs 1.37% (``tail_forward_rates`` in
  the summary).  That single final period is worth -1,058 EUR on the float leg
  (its projected rate is 2.66 bp too high) and -21 EUR on the fixed leg (its DF
  is 1.06e-4 too low).
* ORE's EUR6M curve is LogLinear in the discount factor on its 14 native pillars
  (the curve config sets no ``InterpolationMethod``, so ORE's default applies).
  The monthly grid samples that curve exactly, so QuantLib's LogLinear rebuild is
  exact to ~1e-9 EUR per cashflow except in the nine grid months that contain a
  native pillar, where one kink is smeared over one month; those errors come in
  +/- pairs on consecutive float coupons and net to ~5 EUR in total.
* Hence the "smoother interpolation" variants barely move the price (+7 EUR):
  a smoother curve is *less* like ORE's piecewise-flat-forward curve, and no
  interpolation scheme can know what the curve does after the last pillar.
  Adding the native pillars beyond the grid end (from ORE's
  ``todaysmarketcalibration`` report) or simply ORE's own discount factor on the
  last payment date (from the cashflow report) closes the gap to ~5 EUR; the
  native 14-pillar LogLinear curve closes it to cents (the calibration report
  prints 8 decimals).

Version-skew notes
------------------
* QuantLib 1.43 deprecates ``MonotonicLogCubicDiscountCurve`` (it now emits a
  ``FutureWarning`` and forwards to ``LogCubicDiscountCurve``, whose default
  ``LogCubic()`` is Spline + monotonic).  We call
  ``LogCubicDiscountCurve(..., ql.MonotonicLogCubic())`` explicitly - same
  numbers, no warning.  ``NaturalCubicDiscountCurve`` (cubic in DF) is likewise
  deprecated in favour of ``NaturalLogCubicDiscountCurve``.
* ``ql.Calendar()`` has no public constructor in the 1.43 SWIG wrapper (it is
  the abstract base); to pass an interpolator positionally, the calendar
  argument must be a concrete one - we pass ``ql.NullCalendar()``, which is what
  the C++ default ``Calendar()`` behaves like for a curve built from dates.
* The curves report has no DF at the as-of date (its first row is the 1M point,
  2016-03-07).  ``ql.DiscountCurve`` requires ``(reference date, 1.0)`` as its
  first node, so we prepend it; ORE's curve has the same anchor.
* QuantLib 1.43 wheels are built with par IBOR coupons
  (``IborCoupon.usingAtParCoupons() == True``); the per-coupon forward rates
  match ORE's ``fixingValue`` to 1e-12 wherever the curves agree, so ORE uses the
  same convention.
* No historical fixing is needed: the first EURIBOR fixing is 2016-02-26, after
  the 2016-02-05 as-of.  :func:`build_swap` still checks and, if a past fixing is
  ever required (different as-of), loads it from ORE's own fixings file with
  ``index.addFixing`` rather than letting QuantLib throw "Missing fixing".

Entry points: :func:`run_bridge_test` (returns the summary dict, optionally
writes files) and ``python -m quantstack.risk.bridge_test``.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import warnings
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator, Mapping, Sequence

import numpy as np
import pandas as pd

MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parents[1]
RESULTS_DIR = REPO_ROOT / "results"
DEFAULT_CURVES_CSV = RESULTS_DIR / "risk_curves.csv"
DEFAULT_NPV_CSV = RESULTS_DIR / "risk_npv.csv"
DEFAULT_CASHFLOWS_CSV = RESULTS_DIR / "risk_cashflows.csv"
DEFAULT_ORE_OUTPUT = RESULTS_DIR / "ore_output"
DEFAULT_CALIBRATION_CSV = DEFAULT_ORE_OUTPUT / "todaysmarketcalibration.csv"
DEFAULT_FIXINGS_FILE = MODULE_DIR / "input" / "fixings_20160205.txt"

ASOF = date(2016, 2, 5)
TRADE_ID = "Swap_20y"

#: The article's published bridge numbers (diff = ORE - QuantLib).
ARTICLE = {
    "ore_npv": 1_609_885.84,
    "ql_npv": 1_608_800.94,
    "diff_eur": 1_084.89,
    "diff_bp": 1.08,
}


@dataclass(frozen=True)
class SwapSpec:
    """The article's trade (``Swap_20y`` in ``input/portfolio_swap.xml``).

    Receive 2% fixed (annual, 30/360 Bond Basis, TARGET, Following) against
    EURIBOR-6M (semi-annual, A360, TARGET, Modified Following), 10M EUR,
    2016-03-01 -> 2036-03-01, forward date generation, no end-of-month rule.
    """

    start: date = date(2016, 3, 1)
    end: date = date(2036, 3, 1)
    notional: float = 10_000_000.0
    fixed_rate: float = 0.02
    spread: float = 0.0
    receive_fixed: bool = True
    fixed_tenor: str = "1Y"
    float_tenor: str = "6M"


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------


def _ql():
    import QuantLib as ql  # the standalone wheel, deliberately NOT ORE

    return ql


def _to_date(x) -> date:
    if isinstance(x, date):
        return x if type(x) is date else date(x.year, x.month, x.day)
    if hasattr(x, "dayOfMonth"):  # ql.Date
        return date(x.year(), x.month(), x.dayOfMonth())
    return pd.Timestamp(x).date()


def _ql_date(x):
    d = _to_date(x)
    return _ql().Date(d.day, d.month, d.year)


@contextlib.contextmanager
def _evaluation_date(asof: date) -> Iterator[None]:
    """Set QuantLib's global evaluation date and restore it afterwards.

    ``ql.Settings`` is a process-wide singleton; other modules of the stack
    (pricing) run in the same interpreter under pytest, so we never leave it
    changed behind us.
    """
    ql = _ql()
    settings = ql.Settings.instance()
    old = settings.evaluationDate
    settings.evaluationDate = _ql_date(asof)
    try:
        yield
    finally:
        settings.evaluationDate = old


def _read_ore_csv(path: str | Path) -> pd.DataFrame:
    """Read an ORE CSV report: header may start with ``#``, nulls are ``#N/A``."""
    df = pd.read_csv(path, na_values=["#N/A"])
    df.columns = [str(c).lstrip("#").strip() for c in df.columns]
    return df


# --------------------------------------------------------------------------
# readers
# --------------------------------------------------------------------------


def read_curves_report(path: str | Path) -> pd.DataFrame:
    """ORE ``curves`` report -> DataFrame with a ``date`` column (python dates).

    Works for both ``results/risk_curves.csv`` (the in-memory report saved by
    the risk module) and ORE's own ``curves.csv`` (``#Tenor`` header).
    """
    df = _read_ore_csv(path)
    if "Date" not in df.columns:
        raise ValueError(f"{path}: not an ORE curves report (no 'Date' column)")
    df["date"] = [pd.Timestamp(d).date() for d in df["Date"]]
    return df.sort_values("date").reset_index(drop=True)


def read_ore_npv(path: str | Path, trade_id: str = TRADE_ID) -> float:
    """ORE NPV of ``trade_id`` from an npv report CSV or from ``risk_summary.json``."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text())
        for key in ("npv_base", "ore_npv", "npv"):
            if key in data:
                return float(data[key])
        raise KeyError(f"{path}: no npv_base/ore_npv/npv key")
    df = _read_ore_csv(path)
    rows = df[df["TradeId"].astype(str) == trade_id] if "TradeId" in df else df
    if rows.empty:
        raise KeyError(f"{path}: trade {trade_id!r} not found")
    col = "NPV(Base)" if "NPV(Base)" in rows else "NPV"
    return float(rows[col].iloc[0])


def read_ore_cashflows(path: str | Path, trade_id: str = TRADE_ID) -> pd.DataFrame:
    """ORE ``cashflow`` report -> DataFrame with a ``leg`` column (fixed/float).

    The fixed leg is the one whose ``fixingDate`` is null throughout; this is
    more robust than trusting ``LegNo`` ordering.
    """
    df = _read_ore_csv(path)
    if "TradeId" in df:
        df = df[df["TradeId"].astype(str) == trade_id].copy()
    for col in ("PayDate", "AccrualStartDate", "AccrualEndDate", "fixingDate"):
        if col in df:
            df[col] = [pd.Timestamp(v).date() if isinstance(v, str) and v else pd.NaT
                       for v in df[col]]
    legs = {}
    for leg_no, grp in df.groupby("LegNo"):
        legs[leg_no] = "fixed" if grp["fixingDate"].isna().all() else "float"
    df["leg"] = df["LegNo"].map(legs)
    return df.sort_values(["leg", "PayDate"]).reset_index(drop=True)


def read_native_pillars(path: str | Path, curve_id: str = "EUR6M") -> pd.DataFrame:
    """Native bootstrap pillars of one ORE yield curve from ``todaysmarketcalibration.csv``.

    ORE writes, per pillar, time / zeroRate / discountFactor / forwardRate /
    mdQuote with 8 decimals.  This is the curve ORE *actually* priced with
    (14 pillars for EUR6M: 6M deposit, 2Y..50Y swaps); the 240 x 1M ``curves``
    report is a resampling of it.
    """
    df = _read_ore_csv(path)
    sel = df[(df["MarketObjectType"] == "yieldCurve") & (df["MarketObjectId"] == curve_id)]
    if sel.empty:
        raise KeyError(f"{path}: no yieldCurve {curve_id!r}")
    meta = {r.ResultId: r.ResultValue for r in sel[sel["ResultKey1"].isna()].itertuples()}
    pts = sel[sel["ResultKey1"].notna()]
    wide = pts.pivot_table(index=["ResultKey1", "ResultKey2"], columns="ResultId",
                           values="ResultValue", aggfunc="first").reset_index()
    out = pd.DataFrame({
        "date": [pd.Timestamp(d).date() for d in wide["ResultKey1"]],
        "instrument": wide["ResultKey2"].astype(str),
        "discount": wide["discountFactor"].astype(float),
        "zero_rate": wide["zeroRate"].astype(float),
        "forward_rate": wide.get("forwardRate", pd.Series(np.nan, index=wide.index)).astype(float),
        "time": wide["time"].astype(float),
    }).sort_values("date").reset_index(drop=True)
    out.attrs["day_counter"] = meta.get("dayCounter")
    out.attrs["curve_id"] = curve_id
    return out


def _read_ore_fixings(path: str | Path, index_name: str) -> dict[date, float]:
    """``YYYYMMDD INDEX value`` lines (ORE fixings file), comments skipped."""
    out: dict[date, float] = {}
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        parts = line.split()
        if len(parts) != 3 or line.lstrip().startswith("#") or parts[1] != index_name:
            continue
        d = parts[0]
        out[date(int(d[:4]), int(d[4:6]), int(d[6:8]))] = float(parts[2])
    return out


# --------------------------------------------------------------------------
# QuantLib curve + swap
# --------------------------------------------------------------------------

#: Interpolation variants: key -> (label, builder(dates, dfs, dc) -> curve)
def _curve_builders():
    ql = _ql()

    def zero_linear(dates, dfs, dc):
        t = [dc.yearFraction(dates[0], d) for d in dates]
        z = [-math.log(df) / ti if ti > 0 else float("nan") for df, ti in zip(dfs, t)]
        z[0] = z[1]  # flat zero to the first node == LogLinear DF on that segment
        return ql.ZeroCurve(dates, z, dc, ql.NullCalendar(), ql.Linear(), ql.Continuous, ql.Annual)

    return {
        "loglinear_default": ("DiscountCurve, default interpolation",
                              lambda d, v, dc: ql.DiscountCurve(d, v, dc)),
        "loglinear_explicit": ("DiscountCurve(..., ql.LogLinear())",
                               lambda d, v, dc: ql.DiscountCurve(d, v, dc, ql.NullCalendar(), ql.LogLinear())),
        "monotonic_logcubic": ("LogCubicDiscountCurve(..., ql.MonotonicLogCubic())",
                               lambda d, v, dc: ql.LogCubicDiscountCurve(d, v, dc, ql.NullCalendar(),
                                                                         ql.MonotonicLogCubic())),
        "natural_logcubic": ("NaturalLogCubicDiscountCurve",
                             lambda d, v, dc: ql.NaturalLogCubicDiscountCurve(d, v, dc)),
        "linear_zero": ("ZeroCurve, linear in continuous A365F zero rate", zero_linear),
    }


def build_curve(dates: Sequence, dfs: Sequence[float], asof: date = ASOF,
                method: str = "loglinear_default"):
    """Discount curve in standalone QuantLib from (date, DF) nodes.

    ``(asof, 1.0)`` is prepended when the first node is after ``asof`` (ORE's
    curves report starts at the 1M point).  Actual/365 Fixed is ORE's day counter
    for the EUR curves (``todaysmarketcalibration``: ``Actual/365 (Fixed)``); since
    the nodes are *dates*, the day counter only sets the time axis the
    interpolation runs on, and matching ORE's makes LogLinear reproduce ORE's
    LogLinear curve exactly.  Extrapolation is enabled because the swap's last
    payment is after the last grid date - that is precisely the residual.
    """
    ql = _ql()
    nodes = sorted({_to_date(d): float(v) for d, v in zip(dates, dfs)}.items())
    if nodes[0][0] > asof:
        nodes.insert(0, (asof, 1.0))
    elif nodes[0][0] < asof:
        raise ValueError(f"first curve node {nodes[0][0]} is before the as-of {asof}")
    qd = [_ql_date(d) for d, _ in nodes]
    dfv = [v for _, v in nodes]
    dc = ql.Actual365Fixed()
    builders = _curve_builders()
    if method not in builders:
        raise KeyError(f"unknown curve method {method!r}; choose from {sorted(builders)}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        curve = builders[method][1](qd, dfv, dc)
    curve.enableExtrapolation()
    return curve


def _schedules(spec: SwapSpec):
    ql = _ql()
    cal = ql.TARGET()
    fixed = ql.Schedule(_ql_date(spec.start), _ql_date(spec.end), ql.Period(spec.fixed_tenor), cal,
                        ql.Following, ql.Following, ql.DateGeneration.Forward, False)
    flt = ql.Schedule(_ql_date(spec.start), _ql_date(spec.end), ql.Period(spec.float_tenor), cal,
                      ql.ModifiedFollowing, ql.ModifiedFollowing, ql.DateGeneration.Forward, False)
    return fixed, flt


def build_swap(discount_curve, forward_curve=None, spec: SwapSpec = SwapSpec(),
               asof: date = ASOF, fixings_file: str | Path | None = DEFAULT_FIXINGS_FILE):
    """The identical swap in plain QuantLib, priced by ``DiscountingSwapEngine``.

    Returns ``(swap, info)``.  ``info['historical_fixings']`` lists any past
    EURIBOR fixings that had to be supplied (none for the article's trade: the
    first fixing, 2016-02-26, is after the as-of).  Must be called - and the
    swap priced - with the evaluation date set to ``asof``.
    """
    ql = _ql()
    disc = ql.YieldTermStructureHandle(discount_curve)
    fwd = disc if forward_curve is None else ql.YieldTermStructureHandle(forward_curve)
    index = ql.Euribor6M(fwd)
    fixed_s, float_s = _schedules(spec)
    kind = ql.Swap.Receiver if spec.receive_fixed else ql.Swap.Payer
    swap = ql.VanillaSwap(kind, spec.notional, fixed_s, spec.fixed_rate,
                          ql.Thirty360(ql.Thirty360.BondBasis), float_s, index, spec.spread,
                          ql.Actual360())
    swap.setPricingEngine(ql.DiscountingSwapEngine(disc))

    past = [ql.as_floating_rate_coupon(c).fixingDate() for c in swap.floatingLeg()]
    past = [d for d in past if _to_date(d) <= asof]
    added: list[dict] = []
    if past:
        # Not hit for the article's trade.  ORE would read these from its fixings
        # file; use the same file so both sides see the same number.
        known = _read_ore_fixings(fixings_file, "EUR-EURIBOR-6M") if fixings_file else {}
        for d in past:
            pd_ = _to_date(d)
            if pd_ not in known:
                raise ValueError(f"EURIBOR-6M fixing for {pd_} needed but not in {fixings_file}")
            index.addFixing(d, known[pd_], True)
            added.append({"date": pd_.isoformat(), "value": known[pd_]})
    first_fix = _to_date(ql.as_floating_rate_coupon(swap.floatingLeg()[0]).fixingDate())
    info = {
        "historical_fixing_needed": bool(past),
        "historical_fixings": added,
        "first_fixing_date": first_fix.isoformat(),
        "ibor_par_coupons": bool(ql.IborCoupon.usingAtParCoupons()),
    }
    return swap, info


def price(discount_curve, forward_curve=None, spec: SwapSpec = SwapSpec(), asof: date = ASOF) -> dict:
    """NPV and leg NPVs of the spec'd swap on the given curve(s)."""
    with _evaluation_date(asof):
        swap, info = build_swap(discount_curve, forward_curve, spec, asof)
        last = swap.fixedLeg()[len(swap.fixedLeg()) - 1].date()
        ql_coupon = _ql().as_floating_rate_coupon(swap.floatingLeg()[len(swap.floatingLeg()) - 1])
        out = {
            "npv": float(swap.NPV()),
            "fixed_leg_npv": float(swap.fixedLegNPV()),
            "float_leg_npv": float(swap.floatingLegNPV()),
            "fair_rate": float(swap.fairRate()),
            "df_last_payment": float(discount_curve.discount(last)),
            "last_float_rate": float(ql_coupon.rate()),
            "last_payment_date": _to_date(last).isoformat(),
            **info,
        }
    return out


# --------------------------------------------------------------------------
# comparisons against ORE's cashflow report
# --------------------------------------------------------------------------


def _ql_legs(swap, spec: SwapSpec):
    """Per-cashflow rows for both legs, signed from our (receive-fixed) side."""
    ql = _ql()
    sgn_fixed = 1.0 if spec.receive_fixed else -1.0
    rows = []
    for leg, cfs, sgn in (("fixed", swap.fixedLeg(), sgn_fixed), ("float", swap.floatingLeg(), -sgn_fixed)):
        for i, c in enumerate(cfs):
            cp = ql.as_coupon(c)
            row = {
                "leg": leg, "n": i + 1,
                "pay_date": _to_date(c.date()),
                "accrual_start": _to_date(cp.accrualStartDate()),
                "accrual_end": _to_date(cp.accrualEndDate()),
                "accrual": float(cp.accrualPeriod()),
                "amount": sgn * float(c.amount()),
                "rate": float(cp.rate()),
                "fixing_date": pd.NaT,
            }
            if leg == "float":
                row["fixing_date"] = _to_date(ql.as_floating_rate_coupon(c).fixingDate())
            rows.append(row)
    return pd.DataFrame(rows)


def compare_schedules(ql_rows: pd.DataFrame, ore_cf: pd.DataFrame, source: str = "") -> dict:
    """Do both processes generate the same dates and accruals from the same XML?

    Compares, leg by leg: payment dates, accrual start/end dates, fixing dates
    (float), accrual fractions (30/360 Bond Basis and A360) and fixed amounts.
    Any mismatch is listed; ``all_match`` requires exact date equality.
    """
    out: dict = {"source": source, "mismatches": []}
    for leg in ("fixed", "float"):
        q = ql_rows[ql_rows["leg"] == leg].reset_index(drop=True)
        o = ore_cf[ore_cf["leg"] == leg].reset_index(drop=True)
        out[f"n_{leg}_ql"] = int(len(q))
        out[f"n_{leg}_ore"] = int(len(o))
        same_n = len(q) == len(o)
        checks = {"pay_dates": ("pay_date", "PayDate"),
                  "accrual_start_dates": ("accrual_start", "AccrualStartDate"),
                  "accrual_end_dates": ("accrual_end", "AccrualEndDate")}
        if leg == "float":
            checks["fixing_dates"] = ("fixing_date", "fixingDate")
        for name, (qc, oc) in checks.items():
            ok = same_n and all(a == b for a, b in zip(q[qc], o[oc]))
            out[f"{leg}_{name}_match"] = bool(ok)
            if not ok:
                bad = [(str(a), str(b)) for a, b in zip(q[qc], o[oc]) if a != b]
                out["mismatches"].append({"leg": leg, "field": name, "count": len(bad)
                                          if same_n else "length", "first": bad[:3]})
        if same_n:
            out[f"{leg}_max_accrual_fraction_diff"] = float(np.max(np.abs(q["accrual"] - o["Accrual"])))
        if leg == "fixed" and same_n:
            out["fixed_max_amount_diff_eur"] = float(np.max(np.abs(q["amount"] - o["Amount"])))
    out["fixed_pay_dates"] = [d.isoformat() for d in ql_rows.loc[ql_rows["leg"] == "fixed", "pay_date"]]
    # ORE's own flows.csv prints accruals with 10 decimals (the in-memory report is
    # full precision), so fractions are compared to 1e-9, dates exactly.
    out["accrual_fraction_tolerance"] = 1e-9
    out["all_match"] = bool(not out["mismatches"]
                            and out.get("fixed_max_accrual_fraction_diff", 1) < 1e-9
                            and out.get("float_max_accrual_fraction_diff", 1) < 1e-9)
    return out


def cashflow_table(discount_curve, ore_cf: pd.DataFrame, forward_curve=None,
                   spec: SwapSpec = SwapSpec(), asof: date = ASOF,
                   grid_end: date | None = None) -> pd.DataFrame:
    """QuantLib vs ORE, cashflow by cashflow: amount, DF, PV and their differences."""
    with _evaluation_date(asof):
        swap, _ = build_swap(discount_curve, forward_curve, spec, asof)
        q = _ql_legs(swap, spec)
        q["df"] = [float(discount_curve.discount(_ql_date(d))) for d in q["pay_date"]]
    q["pv"] = q["amount"] * q["df"]
    rows = []
    for leg in ("fixed", "float"):
        a = q[q["leg"] == leg].reset_index(drop=True)
        b = ore_cf[ore_cf["leg"] == leg].reset_index(drop=True)
        n = min(len(a), len(b))
        a, b = a.iloc[:n], b.iloc[:n]
        rows.append(pd.DataFrame({
            "leg": leg, "n": a["n"], "pay_date": a["pay_date"],
            "accrual_start": a["accrual_start"], "accrual_end": a["accrual_end"],
            "fixing_date": a["fixing_date"],
            "ql_rate": a["rate"], "ore_rate": b["fixingValue"] if leg == "float" else b["Coupon"],
            "ql_amount": a["amount"], "ore_amount": b["Amount"],
            "ql_df": a["df"], "ore_df": b["DiscountFactor"],
            "ql_pv": a["pv"], "ore_pv": b["PresentValue"],
        }))
    t = pd.concat(rows, ignore_index=True)
    t["rate_diff_bp"] = (t["ql_rate"] - t["ore_rate"]) * 1e4
    t["df_diff"] = t["ql_df"] - t["ore_df"]
    t["pv_diff_eur"] = t["ql_pv"] - t["ore_pv"]  # QuantLib minus ORE
    if grid_end is not None:
        t["beyond_grid_end"] = [pd_ > grid_end for pd_ in t["pay_date"]]
    return t


def _kink_intervals(grid_dates: Sequence[date], native_dates: Sequence[date]) -> list[tuple[date, date]]:
    """Grid segments (g_i, g_i+1) that contain a native ORE pillar strictly inside.

    On every other segment a LogLinear rebuild from the grid is *exactly* ORE's
    LogLinear curve; only these segments smear a forward-rate kink over a month.
    """
    g = list(grid_dates)
    out = []
    for a, b in zip(g[:-1], g[1:]):
        if any(a < n < b for n in native_dates):
            out.append((a, b))
    return out


# --------------------------------------------------------------------------
# the bridge test
# --------------------------------------------------------------------------


@dataclass
class BridgeResult:
    summary: dict
    variants: pd.DataFrame
    cashflows: pd.DataFrame
    plot_data: dict = field(default_factory=dict)


def _variant_row(key, label, pillars_desc, n_nodes, priced, ore_npv, base_npv, notional):
    diff = ore_npv - priced["npv"]
    return {
        "variant": key, "curve": label, "pillars": pillars_desc, "n_nodes": int(n_nodes),
        "ql_npv": priced["npv"], "diff_eur": diff, "diff_bp": diff / notional * 1e4,
        "change_vs_article_rebuild_eur": priced["npv"] - base_npv,
        "fixed_leg_npv": priced["fixed_leg_npv"], "float_leg_npv": priced["float_leg_npv"],
        "df_last_payment": priced["df_last_payment"], "last_float_rate": priced["last_float_rate"],
    }


def compute_bridge(curves_csv: str | Path = DEFAULT_CURVES_CSV, npv_csv: str | Path = DEFAULT_NPV_CSV,
                   cashflows_csv: str | Path | None = "auto",
                   calibration_csv: str | Path | None = "auto",
                   spec: SwapSpec = SwapSpec(), asof: date = ASOF,
                   discount_column: str = "EUR", forward_column: str = "EUR-EURIBOR-6M") -> BridgeResult:
    """Everything the bridge test computes, as a summary dict plus tables.

    ``cashflows_csv`` / ``calibration_csv`` = ``"auto"`` look for the risk
    module's outputs next to ``curves_csv`` (``risk_cashflows.csv``, then
    ``ore_output/flows.csv``) and in ``ore_output/todaysmarketcalibration.csv``;
    ``None`` disables them.  The core test (rebuild + reprice + diff) only
    needs the curves report and the NPV.
    """
    ql = _ql()
    curves_csv, npv_csv = Path(curves_csv), Path(npv_csv)
    rep = read_curves_report(curves_csv)
    if discount_column not in rep:
        raise KeyError(f"{curves_csv}: no column {discount_column!r}; columns {list(rep.columns)}")
    ore_npv = read_ore_npv(npv_csv)
    grid_dates = list(rep["date"])
    grid_df = rep[discount_column].astype(float).to_numpy()
    grid_end = grid_dates[-1]
    single_curve = (forward_column not in rep
                    or bool(np.max(np.abs(rep[forward_column].to_numpy() - grid_df)) == 0.0))
    fwd_df = None if single_curve else rep[forward_column].astype(float).to_numpy()

    # market configuration, if the risk module's summary is next to the npv file
    market_cfg = None
    rs = npv_csv.parent / "risk_summary.json"
    if rs.exists():
        with contextlib.suppress(Exception):
            market_cfg = json.loads(rs.read_text()).get("market_configuration")

    # optional inputs ---------------------------------------------------------
    def _auto(val, candidates):
        if val is None:
            return None
        if val != "auto":
            if not Path(val).exists():
                raise FileNotFoundError(val)
            return Path(val)
        return next((c for c in candidates if c.exists()), None)

    base = curves_csv.parent
    cf_path = _auto(cashflows_csv, [base / "risk_cashflows.csv", base / "ore_output" / "flows.csv",
                                    DEFAULT_CASHFLOWS_CSV, DEFAULT_ORE_OUTPUT / "flows.csv"])
    cal_path = _auto(calibration_csv, [base / "ore_output" / "todaysmarketcalibration.csv",
                                       DEFAULT_CALIBRATION_CSV])
    ore_cf = read_ore_cashflows(cf_path) if cf_path else None
    native_disc_id = "EUR6M" if single_curve else ("EUR1D" if market_cfg in (None, "xois_eur") else "EUR6M")
    native = native_fwd = None
    if cal_path:
        with contextlib.suppress(KeyError):
            native = read_native_pillars(cal_path, native_disc_id)
            native_fwd = native if single_curve else read_native_pillars(cal_path, "EUR6M")

    def curves_for(method, extra=None, extra_fwd=None, nodes=None, nodes_fwd=None):
        d_nodes = nodes if nodes is not None else list(zip(grid_dates, grid_df)) + (extra or [])
        disc = build_curve([d for d, _ in d_nodes], [v for _, v in d_nodes], asof, method)
        fwd = None
        if not single_curve:
            f_nodes = nodes_fwd if nodes_fwd is not None else list(zip(grid_dates, fwd_df)) + (extra_fwd or [])
            fwd = build_curve([d for d, _ in f_nodes], [v for _, v in f_nodes], asof, method)
        return disc, fwd, len(d_nodes) + (1 if d_nodes[0][0] > asof else 0)

    # 1. the article's rebuild -------------------------------------------------
    disc0, fwd0, n0 = curves_for("loglinear_default")
    base_p = price(disc0, fwd0, spec, asof)
    ql_npv = base_p["npv"]
    diff = ore_npv - ql_npv

    # 2. variants ---------------------------------------------------------------
    grid_desc = f"asof + {len(grid_dates)} x 1M grid (to {grid_end})"
    rows = []
    for key, (label, _) in _curve_builders().items():
        d, f, n = curves_for(key)
        p = base_p if key == "loglinear_default" else price(d, f, spec, asof)
        rows.append(_variant_row(f"grid_{key}", ("ql." + label), grid_desc, n, p, ore_npv, ql_npv,
                                 spec.notional))
    if ore_cf is not None and single_curve:
        tail = ore_cf[ore_cf["PayDate"] > grid_end][["PayDate", "DiscountFactor"]].drop_duplicates("PayDate")
        extra = list(zip(tail["PayDate"], tail["DiscountFactor"].astype(float)))
        if extra:
            d, f, n = curves_for("loglinear_default", extra=extra)
            rows.append(_variant_row(
                "grid_plus_ore_cashflow_df_tail", "ql.DiscountCurve (LogLinear)",
                f"grid + ORE cashflow-report DF on {len(extra)} payment date(s) after {grid_end}",
                n, price(d, f, spec, asof), ore_npv, ql_npv, spec.notional))
    if native is not None:
        ntail = native[native["date"] > grid_end]
        extra = list(zip(ntail["date"], ntail["discount"]))
        extra_f = None
        if not single_curve:
            nft = native_fwd[native_fwd["date"] > grid_end]
            extra_f = list(zip(nft["date"], nft["discount"]))
        d, f, n = curves_for("loglinear_default", extra=extra, extra_fwd=extra_f)
        rows.append(_variant_row(
            "grid_plus_native_tail", "ql.DiscountCurve (LogLinear)",
            f"grid + {len(extra)} native ORE {native_disc_id} pillars after {grid_end} "
            f"(todaysmarketcalibration, 8 dp)", n, price(d, f, spec, asof), ore_npv, ql_npv, spec.notional))
        nodes = list(zip(native["date"], native["discount"]))
        nodes_f = list(zip(native_fwd["date"], native_fwd["discount"])) if not single_curve else None
        d, f, n = curves_for("loglinear_default", nodes=nodes, nodes_fwd=nodes_f)
        rows.append(_variant_row(
            "native_pillars_loglinear", "ql.DiscountCurve (LogLinear)",
            f"asof + {len(nodes)} native ORE {native_disc_id} pillars only (todaysmarketcalibration, 8 dp)",
            n, price(d, f, spec, asof), ore_npv, ql_npv, spec.notional))
    variants = pd.DataFrame(rows)
    variants["abs_diff_eur"] = variants["diff_eur"].abs()
    variants["gap_closed_pct"] = (1 - variants["abs_diff_eur"] / abs(diff)) * 100 if diff else 0.0

    vmap = variants.set_index("variant")
    smooth = vmap.loc[["grid_monotonic_logcubic", "grid_natural_logcubic"]]
    smoother_closer = bool((smooth["abs_diff_eur"] < abs(diff)).any())

    # 3. attribution --------------------------------------------------------------
    attribution: dict = {"convention": "components of diff = ore_npv - ql_npv; they sum to diff"}
    if "grid_plus_native_tail" in vmap.index:
        tail_npv = vmap.loc["grid_plus_native_tail", "ql_npv"]
        nat_npv = vmap.loc["native_pillars_loglinear", "ql_npv"]
        attribution.update({
            "method": "native ORE pillars (todaysmarketcalibration)",
            "extrapolation_beyond_grid_end_eur": tail_npv - ql_npv,
            "interpolation_within_grid_eur": nat_npv - tail_npv,
            "residual_vs_ore_eur": ore_npv - nat_npv,
        })
    elif "grid_plus_ore_cashflow_df_tail" in vmap.index:
        tail_npv = vmap.loc["grid_plus_ore_cashflow_df_tail", "ql_npv"]
        attribution.update({
            "method": "ORE cashflow-report DF on the payment date(s) after the grid end",
            "extrapolation_beyond_grid_end_eur": tail_npv - ql_npv,
            "interpolation_within_grid_eur": ore_npv - tail_npv,
            "residual_vs_ore_eur": None,
        })
    if "extrapolation_beyond_grid_end_eur" in attribution and diff:
        attribution["extrapolation_share_pct"] = attribution["extrapolation_beyond_grid_end_eur"] / diff * 100

    # 4. schedules + per-cashflow table ------------------------------------------
    schedule = {"source": None, "all_match": None, "note": "no ORE cashflow report found"}
    cft = pd.DataFrame()
    clean_max = None
    if ore_cf is not None:
        with _evaluation_date(asof):
            swap, _ = build_swap(disc0, fwd0, spec, asof)
            qrows = _ql_legs(swap, spec)
        schedule = compare_schedules(qrows, ore_cf, os.path.relpath(cf_path, REPO_ROOT)
                                     if str(cf_path).startswith(str(REPO_ROOT)) else str(cf_path))
        cft = cashflow_table(disc0, ore_cf, fwd0, spec, asof, grid_end)
        if native is not None:
            kinks = _kink_intervals([asof] + grid_dates, list(native["date"]))

            def in_kink(d):
                return any(a < d < b for a, b in kinks)

            cft["in_native_pillar_month"] = [
                bool(in_kink(p) or (leg == "float" and in_kink(s)))
                for leg, p, s in zip(cft["leg"], cft["pay_date"], cft["accrual_start"])]
            clean = cft[~cft["in_native_pillar_month"] & ~cft["beyond_grid_end"]]
            # a float coupon's PV also depends on its accrual start DF, handled above
            clean_max = float(clean["pv_diff_eur"].abs().max()) if len(clean) else None

    # forward rate over the stretch past the grid end: extrapolated vs ORE's own
    tail_fwd = None
    if ore_cf is not None:
        lp = date.fromisoformat(base_p["last_payment_date"])
        ore_lp = ore_cf.loc[ore_cf["PayDate"] == lp, "DiscountFactor"]
        if lp > grid_end and len(ore_lp):
            tau = (lp - grid_end).days / 365.0
            df_ge = float(grid_df[-1])
            tail_fwd = {
                "from": grid_end.isoformat(), "to": lp.isoformat(),
                "convention": "continuous, Actual/365F, from DF(grid end) and DF(last payment)",
                "ql_extrapolated": math.log(df_ge / disc0.discount(_ql_date(lp))) / tau,
                "ore": math.log(df_ge / float(ore_lp.iloc[0])) / tau,
            }
            if native is not None:
                after = native[native["date"] > grid_end].head(2)
                if len(after) == 2:
                    (d1, v1), (d2, v2) = zip(after["date"], after["discount"])
                    tail_fwd["ore_native_segment_after_grid_end"] = {
                        "from": d1.isoformat(), "to": d2.isoformat(),
                        "forward": math.log(v1 / v2) / ((d2 - d1).days / 365.0)}

    # 5. plot data -------------------------------------------------------------------
    plot_days = [asof + timedelta(days=i) for i in range(0, (spec.end - asof).days + 45, 3)]
    plot_data = {
        "grid_dates": grid_dates, "grid_df": grid_df, "asof": asof, "grid_end": grid_end,
        "days": plot_days,
        "ql_df": np.array([disc0.discount(_ql_date(d)) for d in plot_days]),
        "last_payment": date.fromisoformat(base_p["last_payment_date"]),
    }
    if native is not None:
        dn, _, _ = curves_for("loglinear_default", nodes=list(zip(native["date"], native["discount"])))
        plot_data["native_dates"] = list(native["date"])
        plot_data["native_df"] = native["discount"].to_numpy()
        plot_data["native_curve_df"] = np.array([dn.discount(_ql_date(d)) for d in plot_days])
    if not cft.empty:
        plot_data["cashflows"] = cft

    # 6. summary -----------------------------------------------------------------------
    def rel(p):
        if p is None:
            return None
        p = Path(p).resolve()
        return os.path.relpath(p, REPO_ROOT) if str(p).startswith(str(REPO_ROOT)) else str(p)

    diff_bp = diff / spec.notional * 1e4
    ore_fixed = ore_float = None
    if ore_cf is not None:
        ore_fixed = float(ore_cf.loc[ore_cf["leg"] == "fixed", "PresentValue"].sum())
        ore_float = float(ore_cf.loc[ore_cf["leg"] == "float", "PresentValue"].sum())
    last_rows = cft[cft.get("beyond_grid_end", pd.Series(False, index=cft.index))] if not cft.empty else cft
    summary = {
        "module": "bridge",
        "quantlib_version": ql.__version__,
        "asof": asof.isoformat(),
        "trade_id": TRADE_ID,
        "market_configuration": market_cfg,
        "single_curve": single_curve,
        "discount_column": discount_column,
        "forward_column": discount_column if single_curve else forward_column,
        "curves_report": {
            "path": rel(curves_csv), "n_grid_dates": len(grid_dates),
            "first_date": grid_dates[0].isoformat(), "last_date": grid_end.isoformat(),
            "columns": [c for c in rep.columns if c not in ("date",)],
            "has_zero_rates": any("zero" in c.lower() for c in rep.columns),
            "note": ("discount factors only, no zero rates; grid = asof + k x 1M, k = 1..240, "
                     "so it ends before the swap's last payment. ORE's native pillars (with zero "
                     "and forward rates, 8 dp) are in ore_output/todaysmarketcalibration.csv."),
        },
        "swap": {"start": spec.start.isoformat(), "end": spec.end.isoformat(), "notional": spec.notional,
                 "fixed_rate": spec.fixed_rate, "receive_fixed": spec.receive_fixed,
                 "last_payment_date": base_p["last_payment_date"],
                 "days_beyond_grid_end": (date.fromisoformat(base_p["last_payment_date"]) - grid_end).days},
        "ore_npv": ore_npv,
        "ql_npv": ql_npv,
        "diff_eur": diff,
        "diff_bp": diff_bp,
        "diff_convention": "diff = ore_npv - ql_npv; bp of notional",
        "ql_fixed_leg_npv": base_p["fixed_leg_npv"],
        "ql_float_leg_npv": base_p["float_leg_npv"],
        "ore_fixed_leg_pv": ore_fixed,
        "ore_float_leg_pv": ore_float,
        "historical_fixing_needed": base_p["historical_fixing_needed"],
        "historical_fixings_added": base_p["historical_fixings"],
        "first_fixing_date": base_p["first_fixing_date"],
        "ibor_par_coupons": base_p["ibor_par_coupons"],
        "schedule_match": schedule,
        "variants": variants.to_dict(orient="records"),
        "smoother_interpolation_closer": smoother_closer,
        "gap_attribution": attribution,
        "beyond_grid_cashflows": [
            {"leg": r.leg, "pay_date": r.pay_date.isoformat(), "pv_diff_eur": r.pv_diff_eur,
             "rate_diff_bp": r.rate_diff_bp, "df_diff": r.df_diff}
            for r in last_rows.itertuples()] if not last_rows.empty else [],
        "tail_forward_rates": tail_fwd,
        "max_abs_pv_diff_clean_cashflows_eur": clean_max,
        "native_curve": None if native is None else {
            "source": rel(cal_path), "curve_id": native_disc_id, "n_pillars": int(len(native)),
            "pillar_dates": [d.isoformat() for d in native["date"]],
            "day_counter": native.attrs.get("day_counter"),
            "interpolation": "LogLinear on discount factors (ORE default; the grid reproduces it to "
                             "machine precision outside the months holding a native pillar)",
        },
        "files": {"cashflows_input": rel(cf_path), "calibration_input": rel(cal_path)},
    }
    summary["article_comparison"] = {
        "article": dict(ARTICLE),
        "ours": {"ore_npv": ore_npv, "ql_npv": ql_npv, "diff_eur": diff, "diff_bp": diff_bp},
        "abs_diff": {"ore_npv": ore_npv - ARTICLE["ore_npv"], "ql_npv": ql_npv - ARTICLE["ql_npv"],
                     "diff_eur": diff - ARTICLE["diff_eur"], "diff_bp": diff_bp - ARTICLE["diff_bp"]},
        "notes": _diagnosis(summary),
    }
    return BridgeResult(summary=summary, variants=variants, cashflows=cft, plot_data=plot_data)


def _diagnosis(s: Mapping) -> list[str]:
    """Plain-English reading of the numbers (goes into the JSON)."""
    notes = [
        f"Same inputs as the article (ORE Example_9 files, libor configuration, 240 x 1M curves grid): "
        f"ORE {s['ore_npv']:,.2f} vs QuantLib {s['ql_npv']:,.2f}, gap {s['diff_eur']:,.2f} EUR = "
        f"{s['diff_bp']:.2f} bp.",
    ]
    sm = s.get("schedule_match") or {}
    if sm.get("all_match"):
        notes.append(f"Schedules agree exactly with ORE's cashflow report: {sm['n_fixed_ql']} fixed and "
                     f"{sm['n_float_ql']} float payment dates, accrual dates, fixing dates and accrual "
                     f"fractions - both processes share QuantLib's TARGET calendar, 30/360 and A360.")
    a = s.get("gap_attribution") or {}
    if "extrapolation_beyond_grid_end_eur" in a:
        notes.append(
            f"The gap is not mainly interpolation: {a['extrapolation_beyond_grid_end_eur']:,.2f} EUR "
            f"({a.get('extrapolation_share_pct', float('nan')):.1f}%) comes from extrapolating past the "
            f"last grid date {s['curves_report']['last_date']} to the final payment "
            f"{s['swap']['last_payment_date']} ({s['swap']['days_beyond_grid_end']} days); interpolation "
            f"inside the grid accounts for {a['interpolation_within_grid_eur']:,.2f} EUR.")
    v = {r["variant"]: r for r in s.get("variants", [])}
    if "grid_monotonic_logcubic" in v:
        notes.append(
            f"Smoother interpolation on the same grid moves the price by only "
            f"{v['grid_monotonic_logcubic']['change_vs_article_rebuild_eur']:+,.2f} EUR (monotonic log-cubic) / "
            f"{v['grid_natural_logcubic']['change_vs_article_rebuild_eur']:+,.2f} EUR (natural log-cubic): ORE's "
            f"curve is itself LogLinear in DF, so LogLinear is already the right scheme.")
    tf = s.get("tail_forward_rates")
    if tf:
        notes.append(f"Over {tf['from']} -> {tf['to']} QuantLib extrapolates a {tf['ql_extrapolated']:.3%} "
                     f"forward (continuous A365) where ORE's curve implies {tf['ore']:.3%}.")
    if s.get("max_abs_pv_diff_clean_cashflows_eur") is not None:
        notes.append(f"Away from native-pillar months and the grid end, cashflow PVs agree to "
                     f"{s['max_abs_pv_diff_clean_cashflows_eur']:.1e} EUR.")
    return notes


# --------------------------------------------------------------------------
# outputs
# --------------------------------------------------------------------------


def plot_bridge(result: BridgeResult, path: str | Path) -> Path:
    """Two stories in one figure: the curves agree (top), the residual lives at the grid end (bottom)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.dates import DateFormatter, MonthLocator, YearLocator

    ink, ink2, grid_c, surface = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    c1, c2, c3 = "#2a78d6", "#eb6834", "#1baf7a"  # categorical slots 1-3 (validated set)

    pdta, s = result.plot_data, result.summary
    days = pd.to_datetime(pdta["days"])
    gd = pd.to_datetime(pdta["grid_dates"])
    grid_end = pd.Timestamp(pdta["grid_end"])
    last_pay = pd.Timestamp(pdta["last_payment"])

    fig = plt.figure(figsize=(11, 8.2), dpi=110)
    fig.patch.set_facecolor(surface)
    gs = fig.add_gridspec(2, 3, height_ratios=[1.05, 1], hspace=0.42, wspace=0.28)
    ax1 = fig.add_subplot(gs[0, :2])
    ax2 = fig.add_subplot(gs[0, 2])
    ax3 = fig.add_subplot(gs[1, :])

    def style(ax):
        ax.set_facecolor(surface)
        ax.grid(True, color=grid_c, lw=0.6)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(ink2)
        ax.tick_params(colors=ink2, labelsize=8.5)

    # (a) full curve
    style(ax1)
    ax1.plot(days, pdta["ql_df"], color=c1, lw=2, label="QuantLib DiscountCurve (LogLinear) on ORE grid")
    ax1.plot(gd, pdta["grid_df"], "o", ms=3, color=ink2, alpha=0.8, label="ORE curves report, 240 x 1M")
    if "native_dates" in pdta:
        nd = pd.to_datetime(pdta["native_dates"])
        m = nd <= days.max()
        ax1.plot(nd[m], pdta["native_df"][m], "D", ms=8, color=c2, mec=surface, mew=1.5,
                 label="ORE native EUR6M pillars", zorder=5)
    ax1.axvline(grid_end, color=ink2, lw=0.8, ls="--")
    ax1.set_xlim(days.min(), days.max())
    ax1.set_ylabel("Discount factor", color=ink)
    ax1.set_xlabel("Date", color=ink)
    ax1.xaxis.set_major_locator(YearLocator(4))
    ax1.xaxis.set_major_formatter(DateFormatter("%Y"))
    ax1.set_title("EUR6M discount curve: ORE nodes vs QuantLib rebuild", color=ink, fontsize=10, loc="left")
    leg = ax1.legend(frameon=False, fontsize=8.5, loc="lower left")
    for t in leg.get_texts():
        t.set_color(ink)

    # (b) zoom at the grid end
    style(ax2)
    lo, hi = grid_end - pd.Timedelta(days=100), last_pay + pd.Timedelta(days=12)
    m = (days >= lo) & (days <= hi)
    ax2.plot(days[m], pdta["ql_df"][m], color=c1, lw=2, label="QuantLib (extrapolated)")
    if "native_curve_df" in pdta:
        ax2.plot(days[m], pdta["native_curve_df"][m], color=c2, lw=2, label="ORE native curve")
    mg = (gd >= lo) & (gd <= hi)
    ax2.plot(gd[mg], pdta["grid_df"][mg], "o", ms=8, color=ink2, mec=surface, mew=1.5, label="ORE grid")
    cft = pdta.get("cashflows")
    if cft is not None and not cft.empty:
        lastrow = cft[cft["pay_date"] == pdta["last_payment"]].iloc[0]
        ax2.plot([last_pay], [lastrow["ore_df"]], "*", ms=12, color=c3, mec=surface, mew=1,
                 label="ORE DF, last payment", zorder=6)
    ax2.axvline(grid_end, color=ink2, lw=0.8, ls="--")
    ax2.axvline(last_pay, color=ink2, lw=0.8, ls=":")
    ax2.text(grid_end, 0.99, f"grid end {grid_end:%d %b} ", transform=ax2.get_xaxis_transform(),
             color=ink2, fontsize=7.5, va="top", ha="right")
    ax2.text(last_pay, 0.91, f"last payment {last_pay:%d %b} ", transform=ax2.get_xaxis_transform(),
             color=ink2, fontsize=7.5, va="top", ha="right")
    ax2.xaxis.set_major_locator(MonthLocator(bymonthday=1))
    ax2.xaxis.set_major_formatter(DateFormatter("%b %y"))
    ax2.set_xlim(lo, hi)
    ax2.tick_params(axis="x", labelrotation=30)
    ax2.set_xlabel("Date", color=ink)
    ax2.set_ylabel("Discount factor", color=ink)
    ax2.set_title("Zoom: past the grid end", color=ink, fontsize=10, loc="left")
    leg = ax2.legend(frameon=False, fontsize=7.5, loc="lower left")
    for t in leg.get_texts():
        t.set_color(ink)

    # (c) per-cashflow PV difference
    style(ax3)
    clip = 80.0
    if cft is not None and not cft.empty:
        width = 55
        for leg_name, color, off in (("fixed", c1, -width / 2), ("float", c2, width / 2)):
            sub = cft[cft["leg"] == leg_name]
            x = pd.to_datetime(sub["pay_date"]) + pd.to_timedelta(off, unit="D")
            y = sub["pv_diff_eur"].clip(-clip, clip)
            ax3.bar(x, y, width=width, color=color, label=f"{leg_name} leg", edgecolor=surface, lw=0.8)
            for xi, yi in zip(x, sub["pv_diff_eur"]):
                if abs(yi) > clip:
                    ax3.annotate(f"{yi:,.0f} EUR {leg_name} coupon (off scale)",
                                 (xi, -clip if yi < 0 else clip),
                                 xytext=(-40, 6 if yi < 0 else -12),
                                 textcoords="offset points", color=ink, fontsize=8, ha="right",
                                 arrowprops=dict(arrowstyle="-", color=ink2, lw=0.8))
        ax3.set_ylim(-clip * 1.15, clip * 1.15)
    ax3.axhline(0, color=ink2, lw=0.8)
    ax3.axvline(grid_end, color=ink2, lw=0.8, ls="--")
    ax3.set_ylabel(f"PV QuantLib - ORE (EUR), clipped at +/-{clip:.0f}", color=ink)
    ax3.set_xlabel("Payment date", color=ink)
    ax3.xaxis.set_major_locator(YearLocator(2))
    ax3.xaxis.set_major_formatter(DateFormatter("%Y"))
    a = s.get("gap_attribution", {})
    sub_t = "Per-cashflow PV difference"
    if "extrapolation_beyond_grid_end_eur" in a:
        sub_t += (f": {a['extrapolation_beyond_grid_end_eur']:,.0f} EUR from the last period beyond the "
                  f"grid, {a['interpolation_within_grid_eur']:,.1f} EUR from +/- pairs in native-pillar months")
    ax3.set_title(sub_t, color=ink, fontsize=10, loc="left")
    leg = ax3.legend(frameon=False, fontsize=8.5, loc="upper left")
    for t in leg.get_texts():
        t.set_color(ink)

    fig.suptitle("Bridge test: ORE-bootstrapped curve repriced in standalone QuantLib, 20y EUR IRS",
                 x=0.06, ha="left", color=ink, fontsize=12, y=0.985)
    fig.text(0.06, 0.935,
             f"ORE {s['ore_npv']:,.2f} EUR   QuantLib {s['ql_npv']:,.2f} EUR   gap {s['diff_eur']:,.2f} EUR "
             f"= {s['diff_bp']:.2f} bp of 10M   (QuantLib {s['quantlib_version']}, as of {s['asof']})",
             color=ink2, fontsize=9)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.89, bottom=0.07)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=surface)
    plt.close(fig)
    return path


def write_outputs(result: BridgeResult, results_dir: str | Path = RESULTS_DIR,
                  make_figure: bool = True) -> dict[str, str]:
    """results/bridge_summary.json, bridge_variants.csv, bridge_cashflows.csv, the figure."""
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    vpath = results_dir / "bridge_variants.csv"
    result.variants.to_csv(vpath, index=False, float_format="%.10g")
    written["variants"] = vpath
    if not result.cashflows.empty:
        cpath = results_dir / "bridge_cashflows.csv"
        result.cashflows.to_csv(cpath, index=False, float_format="%.12g")
        written["cashflows"] = cpath
    if make_figure:
        written["figure"] = plot_bridge(result, results_dir / "figures" / "bridge_discount_curve.png")

    def rel(p):
        p = Path(p).resolve()
        return os.path.relpath(p, REPO_ROOT) if str(p).startswith(str(REPO_ROOT)) else str(p)

    result.summary["files"].update({k: rel(v) for k, v in written.items()})
    spath = results_dir / "bridge_summary.json"
    result.summary["files"]["summary"] = rel(spath)
    spath.write_text(json.dumps(result.summary, indent=2, default=_json_default) + "\n")
    written["summary"] = spath
    return {k: str(v) for k, v in written.items()}


def _json_default(o):
    if isinstance(o, (date, pd.Timestamp)):
        return o.isoformat()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    if o is pd.NaT:
        return None
    return str(o)


def run_bridge_test(curves_csv: str | Path = DEFAULT_CURVES_CSV, npv_csv: str | Path = DEFAULT_NPV_CSV,
                    *, cashflows_csv: str | Path | None = "auto", calibration_csv: str | Path | None = "auto",
                    results_dir: str | Path | None = None, make_figure: bool = True) -> dict:
    """Rebuild ORE's curve in QuantLib, reprice the swap, diagnose the gap.

    Returns the summary dict (JSON-safe apart from nothing: dates are ISO
    strings) with ``ore_npv``, ``ql_npv``, ``diff_eur`` (ORE - QuantLib),
    ``diff_bp``, ``variants`` (list of rows), ``schedule_match`` and
    ``gap_attribution``.  With ``results_dir`` it also writes
    ``bridge_summary.json``, ``bridge_variants.csv``, ``bridge_cashflows.csv``
    and ``figures/bridge_discount_curve.png`` there.
    """
    res = compute_bridge(curves_csv, npv_csv, cashflows_csv=cashflows_csv, calibration_csv=calibration_csv)
    if results_dir is not None:
        write_outputs(res, results_dir, make_figure=make_figure)
    return json.loads(json.dumps(res.summary, default=_json_default))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m quantstack.risk.bridge_test",
        description="Rebuild ORE's bootstrapped EUR6M curve in standalone QuantLib and reprice the 20y swap.",
    )
    ap.add_argument("--curves", default=str(DEFAULT_CURVES_CSV), help="ORE curves report (risk_curves.csv)")
    ap.add_argument("--npv", default=str(DEFAULT_NPV_CSV), help="ORE npv report or risk_summary.json")
    ap.add_argument("--cashflows", default="auto", help="ORE cashflow report ('auto', a path, or 'none')")
    ap.add_argument("--calibration", default="auto",
                    help="ORE todaysmarketcalibration.csv ('auto', a path, or 'none')")
    ap.add_argument("--results", default=str(RESULTS_DIR), help="where bridge_* files go")
    ap.add_argument("--no-figure", action="store_true")
    args = ap.parse_args(argv)
    if not Path(args.curves).exists():
        ap.error(f"{args.curves} not found - run `python -m quantstack.risk.run_ore` first")
    none = lambda v: None if str(v).lower() == "none" else v  # noqa: E731
    res = compute_bridge(args.curves, args.npv, cashflows_csv=none(args.cashflows),
                         calibration_csv=none(args.calibration))
    files = write_outputs(res, args.results, make_figure=not args.no_figure)
    s = res.summary
    print(f"ORE NPV       {s['ore_npv']:>16,.2f} EUR   (article {ARTICLE['ore_npv']:,.2f})")
    print(f"QuantLib NPV  {s['ql_npv']:>16,.2f} EUR   (article {ARTICLE['ql_npv']:,.2f})")
    print(f"diff ORE-QL   {s['diff_eur']:>16,.2f} EUR = {s['diff_bp']:.3f} bp of notional "
          f"(article {ARTICLE['diff_eur']:,.2f} = {ARTICLE['diff_bp']} bp)")
    sm = s["schedule_match"]
    print(f"schedules     all_match={sm.get('all_match')}  ({sm.get('n_fixed_ql')} fixed, "
          f"{sm.get('n_float_ql')} float cashflows vs {sm.get('source')})")
    a = s["gap_attribution"]
    if "extrapolation_beyond_grid_end_eur" in a:
        print(f"attribution   extrapolation past {s['curves_report']['last_date']}: "
              f"{a['extrapolation_beyond_grid_end_eur']:,.2f} EUR ({a.get('extrapolation_share_pct', 0):.1f}%), "
              f"interpolation: {a['interpolation_within_grid_eur']:,.2f} EUR, "
              f"residual: {a.get('residual_vs_ore_eur') if a.get('residual_vs_ore_eur') is None else round(a['residual_vs_ore_eur'], 4)} EUR")
    print("variants (diff = ORE - QL):")
    for r in s["variants"]:
        print(f"  {r['variant']:<32} {r['ql_npv']:>15,.2f}  diff {r['diff_eur']:>10,.2f}  "
              f"({r['diff_bp']:+.4f} bp)")
    for k, v in files.items():
        print(f"wrote {k:<10} {os.path.relpath(v, REPO_ROOT) if v.startswith(str(REPO_ROOT)) else v}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
