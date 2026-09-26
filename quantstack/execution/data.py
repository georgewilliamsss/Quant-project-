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
the same close (same timestamp, emitted just before its bar), which switches
the pre-trade balance check back on.  See ``strategy.py`` for why that matters.

Prices are rounded to the instrument's $0.01 tick when the bars are built
(the dataset carries three decimals); the pandas benchmark in ``backtest.py``
uses the unrounded closes, a sub-cent difference.

Timestamps: ``ts_event = ts_init = <bar date> 21:00 UTC`` in nanoseconds,
i.e. the US cash close (16:00 New York during EST; one hour after the close
during EDT, which is harmless for daily bars).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Mapping, Sequence

import pandas as pd

DEFAULT_SYMBOLS: tuple[str, ...] = ("AAPL", "MSFT", "JPM", "JNJ", "XOM", "PG", "HD", "UNH")
DEFAULT_START = "2016-01-01"
DEFAULT_END = "2022-12-28"
DEFAULT_VENUE = "XNAS"
BAR_CLOSE_UTC = pd.Timedelta(hours=21)


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
    """
    from skfolio.datasets import load_sp500_dataset

    symbols = [str(s).upper() for s in symbols]
    df = load_sp500_dataset()
    missing = [s for s in symbols if s not in df.columns]
    if missing:
        raise KeyError(
            f"symbols not in skfolio's sp500 dataset: {missing}; available: {list(df.columns)}"
        )
    df = df.loc[pd.Timestamp(start) : pd.Timestamp(end), symbols].astype(float)
    df = df.dropna(how="any").sort_index()
    df.index = pd.DatetimeIndex(df.index).tz_localize(None)
    df.index.name = "Date"
    if df.empty:
        raise ValueError(f"no prices for {symbols} in {start}..{end}")
    return df


def make_equity(symbol: str, venue: str = DEFAULT_VENUE, price_precision: int = 2):
    """A cash-equity instrument with ``lot_size = 1``.

    ``TestInstrumentProvider.equity`` (nautilus_trader.test_kit.providers) is
    close, but it hard-codes ``lot_size=100`` and AAPL's ISIN for every
    symbol; a lot of 100 would force round-lot positions, which distorts small
    weights on a $1M book.  So we build the ``Equity`` ourselves.
    Equities have ``size_precision`` 0, so quantities are whole shares.
    """
    from nautilus_trader.model.currencies import USD
    from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
    from nautilus_trader.model.instruments import Equity
    from nautilus_trader.model.objects import Price, Quantity

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


def make_instruments(symbols: Iterable[str], venue: str = DEFAULT_VENUE) -> dict:
    """symbol -> ``Equity`` for every symbol."""
    return {s: make_equity(s, venue) for s in symbols}


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
    day has arrived.  NaN closes are skipped.  ``volume`` is the liquidity
    placeholder discussed in the module docstring (keep it large).
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
            if c != c or c <= 0:  # NaN or non-positive
                continue
            px = instruments[s].make_price(Decimal(repr(float(c))))
            bars.append(Bar(bar_types[s], px, px, px, px, vol, t, t))
    return bars


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
    before its bar reaches the strategy (and before any order is sized)."""
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
    "load_prices",
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
