"""Market data for the execution layer: prices in, NautilusTrader ``Bar`` objects out.

Why this module exists
----------------------
NautilusTrader is an event-driven engine: it does not look at a DataFrame, it
replays a time-ordered stream of ``Data`` objects through the same message bus
a live node would use.  So the first job of the execution layer is to turn a
table of closes into that stream, one ``Bar`` per (symbol, day).

Data source (a reproducibility decision)
----------------------------------------
Prices come from skfolio's bundled S&P 500 dataset
(:func:`skfolio.datasets.load_sp500_dataset`): 20 US large caps, daily
*adjusted* closes 1990-01-02 .. 2022-12-28, shipped inside the skfolio wheel.
No network, no API key, no vendor drift -- anyone with the pinned
``requirements.txt`` gets the exact same numbers.  Because the closes are
split- and dividend-adjusted, a buy-and-hold in this data is a *total return*
series (dividends are implicitly reinvested in the price).  The article used
its own eight names from a different source, so its absolute numbers are not
reproducible here; see ``backtest.py`` for the comparison.

Default universe: eight names from the dataset spread over tech, financials,
health care, energy, staples and discretionary -- AAPL, MSFT, JPM, JNJ, XOM,
PG, HD, UNH -- over 2016-01-01 .. 2022-12-28 (the last date in the dataset).

Why ``make_bars`` builds bars by hand (pandas 3 version skew)
-------------------------------------------------------------
Nautilus ships ``nautilus_trader.persistence.wranglers.BarDataWrangler`` to
convert an OHLCV DataFrame into bars.  With nautilus_trader 1.231.0 and
pandas 3.0.6 it fails.  Reproduced in this environment with a 5-row OHLCV
frame and ``BarDataWrangler(bar_type, instrument).process(df)``::

    File "nautilus_trader/persistence/wranglers.pyx", line 779,
        in nautilus_trader.persistence.wranglers.BarDataWrangler._build_bar
      cpdef Bar _build_bar(self, double[:] values, uint64_t ts_event, uint64_t ts_init):
    File "<stringsource>", line 360, in View.MemoryView.memoryview.__cinit__
    ValueError: buffer source array is read-only

The wrangler passes each row of ``df.values`` into a Cython typed memoryview
``double[:]``, which requires a *writable* buffer.  pandas 3 makes
copy-on-write mandatory (the ``mode.copy_on_write`` option is now a no-op), so
``DataFrame.values`` hands out read-only views and the memoryview refuses
them.  Rather than monkey-patch the wrangler or copy arrays to make them
writable, we construct ``Bar`` objects directly in a Python loop.  For
8 symbols x ~1,760 days (~14k bars) this takes a fraction of a second, has no
dependency on wrangler internals, and is the documented route in this stack.

Limitations of close-only data
------------------------------
The dataset carries closes only, so every bar has ``open = high = low =
close``.  Consequences: (i) the simulated exchange sees a single price per
day, so market orders fill exactly at the close of the bar that triggered
them (no intraday path, no slippage -- consistent with the article's "default
fill model, no commissions" simplification); (ii) any indicator that needs a
range (ATR, Parkinson vol, ...) is meaningless on these bars.

Volume is a *liquidity placeholder*, and it matters.  Nautilus' L1 matching
engine uses the bar volume as the displayed size at the close; a market order
larger than that fills the displayed size at the close and the residual one
tick through.  Measured here (3 names, 2018, HRP): with ``volume=1`` (or 0)
every one of 30 orders was split into two fills -- 1 share at the close and
the rest at close + $0.01 -- i.e. 60 fills and a spurious one-tick slippage.
We therefore default to ``volume = 1_000_000_000`` ("unlimited liquidity at
the close"), which gives exactly one fill per order at the close.

The Nautilus ``RiskEngine`` only prices MARKET orders from quote or trade
ticks, never from bars; with bars alone it logs ``Cannot check MARKET order
risk: no prices for ...`` and *skips* the cash-account free-balance check.
:func:`make_close_trades` therefore emits one synthetic trade tick per bar at
the same close and timestamp, which switches the pre-trade balance check back
on.  See ``strategy.py`` for why that matters.  ``backtest.py`` hands the
trades and the bars to the engine in separate ``add_data`` calls (one per
instrument and data type, because Nautilus validates only the first element of
each call) and lets the engine's stable sort merge them: within a timestamp
every close trade precedes every bar, so each symbol's last-trade price is in
the cache before any bar reaches the strategy, and the bars keep the column
order of ``prices`` (the last symbol's bar still arrives last).

Price precision (the tick) is chosen per instrument from the data
------------------------------------------------------------------------
Each close is rounded to its instrument's tick when the bars are built, so
the tick has to fit the price level.  :func:`price_precision_for` picks it
from the smallest positive close of each column:

* smallest close >= 1: precision 2 (a 0.01 tick, at least three significant
  digits).  Every name of skfolio's dataset is in this case, so those bars are
  exactly what they were with the old fixed 0.01 tick;
* smallest close < 1: ``ceil(-log10(min_close)) + 3`` decimals, so the
  smallest close keeps at least four significant digits (0.000793 -> 7
  decimals, 0.0104 -> 5), capped at :data:`MAX_PRICE_PRECISION` = 9.
  (nautilus_trader 1.231.0 here is a high-precision build that accepts up to
  16; ``Equity``, ``Price.from_str``, bars, trade ticks and default-fill-model
  fills were checked at 6-9.)

A fixed 0.01 tick used to turn a 0.004 close into 0.00 (the name was then
skipped and its weight sat in cash, and HRP died on infinite returns) and a
0.012 close into 0.01.  :func:`make_bars` now refuses, with a ``ValueError``
naming the symbol and date, any close that is not positive after rounding.
The pandas benchmark in ``backtest.py`` uses the unrounded closes.

Timestamps: ``ts_event = ts_init = <bar date> 21:00 UTC`` in nanoseconds,
i.e. the US cash close (16:00 New York during EST; one hour after the close
during EDT, which is harmless for daily bars).
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

DEFAULT_SYMBOLS: tuple[str, ...] = ("AAPL", "MSFT", "JPM", "JNJ", "XOM", "PG", "HD", "UNH")
DEFAULT_START = "2016-01-01"
DEFAULT_END = "2022-12-28"
DEFAULT_VENUE = "XNAS"
BAR_CLOSE_UTC = pd.Timedelta(hours=21)
MIN_SYMBOLS = 2
#: Precision used when every close is >= 1 (a 0.01 tick); also the lower bound of a derived one.
DEFAULT_PRICE_PRECISION = 2
#: Upper bound on the derived precision (nautilus standard precision allows 9).
MAX_PRICE_PRECISION = 9
#: Below 1, the smallest close keeps at least this many significant digits.
SUBUNIT_SIGNIFICANT_DIGITS = 4


def validate_symbols(symbols: Iterable[str], min_symbols: int = MIN_SYMBOLS) -> list[str]:
    """Normalise a universe (strip, upper-case) and check it, or raise ``ValueError``.

    At least ``min_symbols`` names (a rebalance needs a portfolio: HRP cannot
    cluster one asset) and no duplicates (a repeated column would feed the
    strategy two bars per day for one instrument).  A bare string is refused
    rather than silently iterated character by character.  Membership in the
    dataset is checked by :func:`load_prices`.
    """
    if isinstance(symbols, str):
        raise ValueError(f"pass a sequence of symbols, not the string {symbols!r}")
    syms = [str(s).strip().upper() for s in symbols]
    if len(syms) < min_symbols:
        raise ValueError(f"need at least {min_symbols} symbols, got {len(syms)}: {syms}")
    dups = sorted({s for s in syms if syms.count(s) > 1})
    if dups:
        raise ValueError(f"duplicate symbols: {dups}")
    return syms


def load_prices(
    symbols: Sequence[str] = DEFAULT_SYMBOLS,
    start: str | pd.Timestamp = DEFAULT_START,
    end: str | pd.Timestamp = DEFAULT_END,
) -> pd.DataFrame:
    """Daily adjusted closes for ``symbols`` between ``start`` and ``end`` (inclusive).

    Returns a float DataFrame indexed by a tz-naive ``DatetimeIndex`` (named
    ``Date``) with one column per symbol, in the order requested.  Rows with a
    missing close for any requested symbol are dropped so that every trading
    day has a bar for every symbol -- the strategy's "act after the last
    symbol's bar of the day" trick relies on a rectangular panel.

    Raises ``ValueError`` for duplicate symbols, symbols that are not in the
    dataset, or a window with no prices.  (A single symbol is allowed here;
    the backtest's own check, :func:`validate_symbols`, asks for two.)
    """
    from skfolio.datasets import load_sp500_dataset

    symbols = validate_symbols(symbols, min_symbols=1)
    df = load_sp500_dataset()
    missing = [s for s in symbols if s not in df.columns]
    if missing:
        raise ValueError(
            f"symbols not in skfolio's sp500 dataset: {missing}; available: {list(df.columns)}"
        )
    df = df.loc[pd.Timestamp(start) : pd.Timestamp(end), symbols].astype(float)
    df = df.dropna(how="any").sort_index()
    df.index = pd.DatetimeIndex(df.index).tz_localize(None)
    df.index.name = "Date"
    if df.empty:
        raise ValueError(f"no prices for {symbols} in {start}..{end}")
    return df


def price_precision_for(closes: Iterable[float]) -> int:
    """Decimals of the price tick for one instrument, from its closes (NaN ignored).

    ``2`` when the smallest positive close is >= 1 (the 0.01 tick already
    keeps three significant digits), else ``ceil(-log10(min_close)) + 3`` so
    the smallest close keeps at least :data:`SUBUNIT_SIGNIFICANT_DIGITS` (4)
    significant digits, capped at :data:`MAX_PRICE_PRECISION` (9).  With no
    positive close at all the default 2 is returned (:func:`make_bars` then
    refuses the series).  Examples: 20.85 -> 2, 1.80 -> 2, 0.5 -> 4,
    0.0104 -> 5, 0.000793 -> 7, 1e-12 -> 9.
    """
    a = np.array(list(closes), dtype=float)
    a = a[np.isfinite(a) & (a > 0)]
    if a.size == 0:
        return DEFAULT_PRICE_PRECISION
    lo = float(a.min())
    if lo >= 1.0:
        return DEFAULT_PRICE_PRECISION
    digits = math.ceil(-math.log10(lo)) + SUBUNIT_SIGNIFICANT_DIGITS - 1
    return int(min(MAX_PRICE_PRECISION, max(DEFAULT_PRICE_PRECISION, digits)))


def price_precisions(prices: pd.DataFrame) -> dict[str, int]:
    """column -> :func:`price_precision_for` of that column, for every column of ``prices``."""
    return {str(c): price_precision_for(prices[c].to_numpy(dtype=float)) for c in prices.columns}


def make_equity(symbol: str, venue: str = DEFAULT_VENUE, price_precision: int = DEFAULT_PRICE_PRECISION):
    """A cash-equity instrument with ``lot_size = 1`` and a ``10**-price_precision`` tick.

    ``TestInstrumentProvider.equity`` (nautilus_trader.test_kit.providers) is
    close, but it hard-codes ``lot_size=100`` and AAPL's ISIN for every
    symbol; a lot of 100 would force round-lot positions, which distorts small
    weights on a $1M book.  So we build the ``Equity`` ourselves.
    Equities have ``size_precision`` 0, so quantities are whole shares.
    ``price_precision`` must be an int in 0..:data:`MAX_PRICE_PRECISION`;
    pick it with :func:`price_precision_for`.
    """
    from nautilus_trader.model.currencies import USD
    from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
    from nautilus_trader.model.instruments import Equity
    from nautilus_trader.model.objects import Price, Quantity

    if isinstance(price_precision, bool) or not isinstance(price_precision, (int, np.integer)) \
            or not 0 <= int(price_precision) <= MAX_PRICE_PRECISION:
        raise ValueError(f"price_precision for {symbol} must be an int in 0..{MAX_PRICE_PRECISION}, "
                         f"got {price_precision!r}")
    price_precision = int(price_precision)
    increment = Price(10.0**-price_precision, price_precision)
    return Equity(
        instrument_id=InstrumentId(Symbol(symbol), Venue(venue)),
        raw_symbol=Symbol(symbol),
        currency=USD,
        price_precision=price_precision,
        price_increment=increment,
        lot_size=Quantity.from_int(1),
        ts_event=0,
        ts_init=0,
    )


def make_instruments(
    symbols: Iterable[str],
    venue: str = DEFAULT_VENUE,
    price_precision: int | Mapping[str, int] = DEFAULT_PRICE_PRECISION,
) -> dict:
    """symbol -> ``Equity`` for every symbol.

    ``price_precision`` is one int for all symbols (default 2, the 0.01 tick)
    or a mapping symbol -> precision, usually :func:`price_precisions` of the
    price panel (``backtest.py`` does that); a symbol missing from the
    mapping raises ``ValueError``.
    """
    symbols = list(symbols)
    if isinstance(price_precision, Mapping):
        missing = [s for s in symbols if str(s) not in price_precision]
        if missing:
            raise ValueError(f"no price_precision for {missing}")
        return {s: make_equity(s, venue, price_precision[str(s)]) for s in symbols}
    return {s: make_equity(s, venue, price_precision) for s in symbols}


def bar_type_for(instrument) -> "BarType":  # noqa: F821 - nautilus type
    """``<SYMBOL>.<VENUE>-1-DAY-LAST-EXTERNAL`` for an instrument."""
    from nautilus_trader.model.data import BarType

    return BarType.from_str(f"{instrument.id}-1-DAY-LAST-EXTERNAL")


def make_bar_types(instruments: Mapping[str, object]) -> dict:
    """symbol -> ``BarType`` for every instrument."""
    return {s: bar_type_for(inst) for s, inst in instruments.items()}


def bar_timestamps_ns(index: pd.DatetimeIndex) -> list[int]:
    """Bar date -> 21:00 UTC that day, as UNIX nanoseconds."""
    idx = pd.DatetimeIndex(index)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    idx = idx.normalize() + BAR_CLOSE_UTC
    return [int(t) for t in idx.as_unit("ns").asi8]


DEFAULT_BAR_VOLUME = 1_000_000_000


def make_bars(
    prices: pd.DataFrame,
    instruments: Mapping[str, object],
    bar_types: Mapping[str, object],
    volume: int = DEFAULT_BAR_VOLUME,
) -> list:
    """Build one Nautilus ``Bar`` per (day, symbol), sorted by ``ts_init``.

    Built directly in a loop instead of via ``BarDataWrangler`` (which raises
    ``ValueError: buffer source array is read-only`` under pandas 3's
    copy-on-write; see the module docstring).  Close-only data: ``open = high
    = low = close``.  Within a day, bars are emitted in the column order of
    ``prices``; the strategy uses that to know when the *last* symbol of the
    day has arrived.  NaN closes are skipped (no bar that day).  ``volume`` is
    the liquidity placeholder discussed in the module docstring (keep it large).

    Each close is rounded to its instrument's tick (``make_price``).  A close
    that is infinite, not positive, or rounds to 0 at that precision raises
    ``ValueError`` naming the symbol and the date: the engine must never mark
    or trade a name at 0 (build the instruments with
    ``make_instruments(..., price_precision=price_precisions(prices))``).
    """
    from nautilus_trader.model.data import Bar
    from nautilus_trader.model.objects import Quantity

    symbols = [c for c in prices.columns if c in instruments]
    if not symbols:
        raise ValueError("no overlap between price columns and instruments")
    ts = bar_timestamps_ns(prices.index)
    vol = Quantity.from_int(int(volume))
    bars = []
    cols = {s: prices[s].to_numpy(dtype=float) for s in symbols}  # read-only is fine here
    for i, t in enumerate(ts):
        for s in symbols:
            c = cols[s][i]
            if c != c:  # NaN: no bar for this symbol today
                continue
            inst = instruments[s]
            if not math.isfinite(c) or c <= 0:
                raise ValueError(f"{s}: close {float(c)!r} on {_day(prices.index[i])} is not a positive finite "
                                 "price; the engine cannot mark or trade it")
            px = inst.make_price(Decimal(repr(float(c))))
            if not px.as_double() > 0:
                raise ValueError(
                    f"{s}: close {float(c)!r} on {_day(prices.index[i])} rounds to {px} at the instrument's "
                    f"price_precision {inst.price_precision}; build the instruments with "
                    "make_instruments(..., price_precision=price_precisions(prices)) or rescale the series")
            bars.append(Bar(bar_types[s], px, px, px, px, vol, t, t))
    return bars


def _day(label) -> str:
    try:
        return pd.Timestamp(label).date().isoformat()
    except (TypeError, ValueError):
        return str(label)


def make_close_trades(bars: Iterable, size: int = DEFAULT_BAR_VOLUME) -> list:
    """One synthetic ``TradeTick`` per bar, at the bar's close and timestamp.

    Purpose: give the ``RiskEngine`` a last-trade price so it can run its
    cash-account ``NOTIONAL_EXCEEDS_FREE_BALANCE`` pre-trade check on MARKET
    orders (it never reads bars).  The trade carries no information beyond
    the bar itself, so it does not move the simulated market.
    """
    from nautilus_trader.model.data import TradeTick
    from nautilus_trader.model.enums import AggressorSide
    from nautilus_trader.model.identifiers import TradeId
    from nautilus_trader.model.objects import Quantity

    qty = Quantity.from_int(int(size))
    return [
        TradeTick(b.bar_type.instrument_id, b.close, qty, AggressorSide.NO_AGGRESSOR,
                  TradeId(f"C{i}"), b.ts_event, b.ts_init)
        for i, b in enumerate(bars)
    ]


def interleave_trades_and_bars(bars: Sequence, trades: Sequence) -> list:
    """``[trade_0, bar_0, trade_1, bar_1, ...]`` so that, after the engine's
    *stable* sort by ``ts_init``, each symbol's close trade is in the cache
    before its bar reaches the strategy (and before any order is sized).

    Kept for callers that need one merged stream.  ``backtest.py`` no longer
    passes this list to ``BacktestEngine.add_data`` in one call: Nautilus
    validates only ``data[0]`` of a call (instrument registered, bar source
    EXTERNAL), so the backtest adds each instrument's trades and bars
    separately (see the module docstring).
    """
    if len(bars) != len(trades):
        raise ValueError("bars and trades must be parallel")
    out: list = []
    for t, b in zip(trades, bars):
        out.append(t)
        out.append(b)
    return out


__all__ = [
    "DEFAULT_SYMBOLS",
    "DEFAULT_START",
    "DEFAULT_END",
    "DEFAULT_VENUE",
    "MIN_SYMBOLS",
    "validate_symbols",
    "load_prices",
    "DEFAULT_PRICE_PRECISION",
    "MAX_PRICE_PRECISION",
    "SUBUNIT_SIGNIFICANT_DIGITS",
    "price_precision_for",
    "price_precisions",
    "make_equity",
    "make_instruments",
    "make_bar_types",
    "bar_type_for",
    "bar_timestamps_ns",
    "make_bars",
    "make_close_trades",
    "interleave_trades_and_bars",
    "DEFAULT_BAR_VOLUME",
]
