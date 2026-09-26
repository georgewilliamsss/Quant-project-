"""The four wires of the stack, as explicit data contracts.

    1. Returns  -> Weights   : the allocator's contract  (skfolio)
    2. Weights  -> Orders    : the execution contract    (NautilusTrader)
    3. Positions-> Risk      : the risk contract         (ORE)
    4. State    -> Screen    : the display contract      (Perspective)

Every module in ``quantstack`` codes against these types, never against each
other's internals.  Keep this file dependency-light: pandas and the standard
library only, so any component can import it without dragging in the others.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping, Protocol, Sequence

import pandas as pd

# --------------------------------------------------------------------------
# 1. Returns -> Weights
# --------------------------------------------------------------------------


class Allocator(Protocol):
    """Anything that turns a returns matrix into portfolio weights.

    ``returns`` is a DataFrame indexed by date with one column per asset,
    holding simple periodic returns.  The result maps asset -> weight, weights
    non-negative and summing to at most 1.0 (long-only, fully or partly
    invested).  skfolio estimators satisfy this via :func:`fit_weights`.
    """

    def __call__(self, returns: pd.DataFrame) -> "Weights": ...


Weights = dict[str, float]
"""asset symbol -> target portfolio weight (fraction of equity)."""


def validate_weights(weights: Mapping[str, float], tol: float = 1e-6) -> Weights:
    """Return a clean copy of ``weights`` or raise ``ValueError``.

    Long-only, no NaNs, sum <= 1 + tol.
    """
    clean: Weights = {}
    for symbol, w in weights.items():
        w = float(w)
        if w != w:  # NaN
            raise ValueError(f"weight for {symbol} is NaN")
        if w < -tol:
            raise ValueError(f"weight for {symbol} is negative: {w}")
        clean[str(symbol)] = max(w, 0.0)
    total = sum(clean.values())
    if total > 1.0 + tol:
        raise ValueError(f"weights sum to {total:.6f} > 1")
    return clean


def fit_weights(estimator, returns: pd.DataFrame) -> Weights:
    """Adapter: any scikit-learn-style estimator exposing ``weights_`` after ``fit``.

    This is the only place the stack touches skfolio's API surface for sizing,
    so swapping the allocator is a one-line change at the call site.
    """
    estimator.fit(returns)
    return validate_weights(dict(zip(returns.columns, estimator.weights_)))


# --------------------------------------------------------------------------
# 2. Weights -> Orders
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class OrderIntent:
    """A target-delta the execution engine should turn into a market order.

    ``delta_qty`` > 0 means buy, < 0 means sell.  Quantities are in units of
    the instrument (shares).  This is deliberately engine-agnostic: the
    NautilusTrader strategy converts these into ``MarketOrder`` objects.
    """

    symbol: str
    delta_qty: float

    @property
    def side(self) -> str:
        return "BUY" if self.delta_qty > 0 else "SELL"


def target_deltas(
    weights: Mapping[str, float],
    equity: float,
    prices: Mapping[str, float],
    positions: Mapping[str, float],
    investment_cap: float = 0.98,
    lot: int = 1,
    min_trade_value: float = 0.0,
) -> list[OrderIntent]:
    """Turn target weights into a list of order intents, sells first.

    * ``equity``     : cash + market value of open positions (cash account).
    * ``prices``     : last known price per symbol.
    * ``positions``  : current signed quantity per symbol (0 if flat).
    * ``investment_cap`` : fraction of equity that may be deployed; the
      remainder is a cash buffer so that market fills at a slightly worse
      price than the last close are not rejected for insufficient funds.
    * ``lot``        : round quantities down to a multiple of this.

    Sells are returned before buys because on a cash account the sells free
    the cash that the buys need; submitting buys first gets them rejected by
    the simulated (and the real) exchange.
    """
    deployable = equity * investment_cap
    intents: list[OrderIntent] = []
    # Iterate in sorted order so the output does not depend on set/hash order
    # (PYTHONHASHSEED): two symbols with the same delta must always come out
    # in the same order, or fills files differ between otherwise identical runs.
    symbols = sorted(set(weights) | {s for s, q in positions.items() if q})
    for symbol in symbols:
        px = prices.get(symbol)
        if px is None or px <= 0:
            continue
        target_qty = int((deployable * weights.get(symbol, 0.0)) / px) // lot * lot
        delta = target_qty - float(positions.get(symbol, 0.0))
        if delta == 0 or abs(delta) * px < min_trade_value:
            continue
        intents.append(OrderIntent(symbol, float(delta)))
    intents.sort(key=lambda o: (o.delta_qty, o.symbol))  # sells first, ties by symbol
    return intents


# --------------------------------------------------------------------------
# 3. Positions -> Risk
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Position:
    """One line of a positions snapshot as the execution engine sees it."""

    symbol: str
    qty: float
    last: float

    @property
    def value(self) -> float:
        return self.qty * self.last


@dataclass
class PositionSnapshot:
    """The book at a point in time.  This is what flows out of execution and
    into both the risk engine and the screen."""

    as_of: date
    positions: list[Position] = field(default_factory=list)
    cash: float = 0.0

    @property
    def market_value(self) -> float:
        return sum(p.value for p in self.positions)

    @property
    def equity(self) -> float:
        return self.cash + self.market_value

    def to_rows(self) -> list[dict]:
        """Rows for the ``positions`` table (see contract 4)."""
        return [
            {"symbol": p.symbol, "qty": p.qty, "last": p.last, "value": p.value}
            for p in self.positions
        ]


POSITIONS_CSV_COLUMNS = ("as_of", "symbol", "qty", "last", "value", "cash")


def write_positions_csv(snapshot: PositionSnapshot, path: str | Path) -> Path:
    """Persist a snapshot as a flat CSV that a *different program* can read.

    The industry separates execution from risk on purpose: ORE reads a file
    that the execution engine wrote, rather than one process marking its own
    homework.  ``quantstack.risk`` turns this file into an ORE portfolio.

    The account's cash is repeated on every row (a flat file has no header
    record); readers take it from the first row.  Files written before the
    ``cash`` column existed still read back, with cash 0.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(POSITIONS_CSV_COLUMNS)
        for p in snapshot.positions:
            w.writerow(
                [snapshot.as_of.isoformat(), p.symbol, p.qty, p.last, p.value, snapshot.cash]
            )
    return path


def read_positions_csv(path: str | Path) -> PositionSnapshot:
    """Inverse of :func:`write_positions_csv`."""
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"no positions in {path}")
    as_of = date.fromisoformat(str(df["as_of"].iloc[0]))
    positions = [
        Position(str(r.symbol), float(r.qty), float(r.last)) for r in df.itertuples()
    ]
    cash = float(df["cash"].iloc[0]) if "cash" in df.columns else 0.0
    return PositionSnapshot(as_of=as_of, positions=positions, cash=cash)


# The equity curve is the other artefact that leaves the execution engine as a
# file: one ``date`` column plus one or more ``equity*`` columns (a backtest
# writes the strategy and its benchmarks side by side, e.g. ``equity_hrp``,
# ``equity_equal_engine``, ``equity_equal_pandas``).
EQUITY_CSV_DATE_COLUMN = "date"
EQUITY_CSV_COLUMN_PREFIX = "equity"


def write_equity_csv(curves: pd.Series | pd.DataFrame, path: str | Path) -> Path:
    """Persist one or more equity curves indexed by date.

    A bare Series is written as the single column ``equity``.  A DataFrame's
    columns are kept as given; every column must start with ``equity``.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(curves, pd.Series):
        frame = curves.rename(EQUITY_CSV_COLUMN_PREFIX).to_frame()
    else:
        frame = curves.copy()
    bad = [c for c in frame.columns if not str(c).startswith(EQUITY_CSV_COLUMN_PREFIX)]
    if bad:
        raise ValueError(f"equity columns must start with '{EQUITY_CSV_COLUMN_PREFIX}': {bad}")
    frame = frame.sort_index()
    frame.index = pd.to_datetime(frame.index).strftime("%Y-%m-%d")
    frame.index.name = EQUITY_CSV_DATE_COLUMN
    frame.to_csv(path, float_format="%.6f")
    return path


def equity_csv_columns(path: str | Path) -> list[str]:
    """The equity curve columns available in an equity CSV, in file order."""
    header = pd.read_csv(path, nrows=0).columns
    return [c for c in header if str(c).startswith(EQUITY_CSV_COLUMN_PREFIX)]


def read_equity_csv(path: str | Path, column: str | None = None) -> pd.Series:
    """Inverse of :func:`write_equity_csv` for one curve.

    ``column`` picks the curve; by default the plain ``equity`` column if it
    exists, else the first ``equity*`` column (the strategy's own curve is
    written first by convention).
    """
    df = pd.read_csv(path)
    if EQUITY_CSV_DATE_COLUMN not in df.columns:
        raise ValueError(f"{path} has no '{EQUITY_CSV_DATE_COLUMN}' column")
    candidates = [c for c in df.columns if str(c).startswith(EQUITY_CSV_COLUMN_PREFIX)]
    if not candidates:
        raise ValueError(f"{path} has no '{EQUITY_CSV_COLUMN_PREFIX}*' column")
    if column is None:
        column = EQUITY_CSV_COLUMN_PREFIX if EQUITY_CSV_COLUMN_PREFIX in candidates else candidates[0]
    if column not in candidates:
        raise ValueError(f"{path} has no column {column!r}; available: {candidates}")
    s = pd.Series(df[column].astype(float).values, index=pd.to_datetime(df[EQUITY_CSV_DATE_COLUMN]))
    s.name = column
    s.index.name = EQUITY_CSV_DATE_COLUMN
    return s.sort_index()


# --------------------------------------------------------------------------
# 4. State -> Screen
# --------------------------------------------------------------------------

POSITIONS_SCHEMA = {"symbol": "string", "qty": "float", "last": "float", "value": "float"}
EQUITY_SCHEMA = {"date": "string", "equity": "float"}
FILLS_SCHEMA = {
    "ts": "string",
    "symbol": "string",
    "side": "string",
    "qty": "float",
    "price": "float",
}


class DashboardSink(Protocol):
    """Where the execution engine pushes state.  Perspective implements this
    with two indexed tables; tests use :class:`RecordingSink`.

    * ``positions`` rows follow ``POSITIONS_SCHEMA`` and are keyed by symbol,
      so an update is an in-place tick, not an append.
    * ``equity`` rows follow ``EQUITY_SCHEMA`` and are keyed by date.
    """

    def update_positions(self, rows: Iterable[dict]) -> None: ...

    def update_equity(self, rows: Iterable[dict]) -> None: ...

    def update_fills(self, rows: Iterable[dict]) -> None: ...


class NullSink:
    """A sink that drops everything.  Lets the backtest run headless."""

    def update_positions(self, rows: Iterable[dict]) -> None:  # noqa: D401
        for _ in rows:
            pass

    def update_equity(self, rows: Iterable[dict]) -> None:
        for _ in rows:
            pass

    def update_fills(self, rows: Iterable[dict]) -> None:
        for _ in rows:
            pass


class RecordingSink:
    """A sink that keeps the last positions row per symbol and every equity
    point in memory.  Useful for tests and for reading the curve back out."""

    def __init__(self) -> None:
        self.positions: dict[str, dict] = {}
        self.equity: dict[str, float] = {}
        self.fills: list[dict] = []

    def update_positions(self, rows: Iterable[dict]) -> None:
        for r in rows:
            self.positions[r["symbol"]] = dict(r)

    def update_equity(self, rows: Iterable[dict]) -> None:
        for r in rows:
            self.equity[r["date"]] = float(r["equity"])

    def update_fills(self, rows: Iterable[dict]) -> None:
        self.fills.extend(dict(r) for r in rows)

    def equity_curve(self) -> pd.Series:
        s = pd.Series(self.equity, dtype=float)
        s.index = pd.to_datetime(s.index)
        return s.sort_index()


__all__: Sequence[str] = (
    "Allocator",
    "Weights",
    "validate_weights",
    "fit_weights",
    "OrderIntent",
    "target_deltas",
    "Position",
    "PositionSnapshot",
    "write_positions_csv",
    "read_positions_csv",
    "POSITIONS_CSV_COLUMNS",
    "EQUITY_CSV_DATE_COLUMN",
    "EQUITY_CSV_COLUMN_PREFIX",
    "write_equity_csv",
    "read_equity_csv",
    "equity_csv_columns",
    "POSITIONS_SCHEMA",
    "EQUITY_SCHEMA",
    "FILLS_SCHEMA",
    "DashboardSink",
    "NullSink",
    "RecordingSink",
)
