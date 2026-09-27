"""``SkfolioRebalance``: a NautilusTrader strategy with skfolio riding inside it.

The shape of the loop (and why)
-------------------------------
NautilusTrader owns the event loop: it replays market data through its
message bus, routes our orders through its ``RiskEngine`` to a simulated
exchange, and books fills into a cash account.  The strategy never loops over
a DataFrame; it reacts to events:

* ``on_bar``  -- one call per (symbol, day).  We append the close to a
  per-instrument ``deque(maxlen=lookback_bars)`` and only *act* once every
  symbol has reported for that timestamp ("wait for the last symbol's bar of
  the day", the article's trick).  Acting on the first bar of the day would
  size the book with a mix of today's and yesterday's prices, and the
  simulated exchange would fill the other symbols at yesterday's close.
* Every ``rebalance_every`` completed days, once every symbol has at least
  ``lookback_bars`` closes, we rebuild the trailing price frame, turn it into
  returns with :func:`window_returns` (which refuses non-finite returns,
  naming the symbol) and ask the allocator for weights.
* ``contracts.target_deltas`` turns weights into share deltas, sells first.
  Quantities are whole shares (floored), so a high-priced name with a small
  weight lands under its target; the book right after each rebalance's fills
  is recorded as *achieved* weights (``achieved_history``) next to the
  targets (``weights_history``).
* ``on_order_filled`` pushes a fills row; rejections / denials are counted
  and logged.
* Once per day one batch goes to the sink: one ``update_equity`` call and one
  ``update_positions`` call carrying every symbol's row.

Sells first is necessary but not sufficient (measured, nautilus 1.231.0)
------------------------------------------------------------------------
The article: on a cash account, buys submitted before the sells that fund
them get rejected for insufficient funds, so submit sells first.  Here is
what we measured with 3 names over 2018 (HRP, lookback 60, monthly; with a
last-trade price available to the RiskEngine, see ``data.make_close_trades``):

=========================================  ======  =====  ======  =========
order mode                                 orders  fills  denied  outcome
=========================================  ======  =====  ======  =========
``buys_first`` (all at once)               30      22     6       halted
``sells_first`` (all at once, article)     30      24     6       completes
``two_phase`` (sells, then buys on fill)   30      30     0       completes
=========================================  ======  =====  ======  =========

Why ``sells_first`` alone still gets buys denied: the simulated venue
*queues* commands (``use_message_queue=True``, the default) and fills them
after ``on_bar`` returns, but the RiskEngine checks each order *at
submission*, when none of the sells have filled yet, so a buy larger than the
2% cash buffer is denied with ``NOTIONAL_EXCEEDS_FREE_BALANCE``.  (The
article's version evidently filled sells before checking buys; with
``use_message_queue=False`` we reproduce exactly that: sells-first gives 0
denials, buys-first 7.)  And ``buys_first`` is worse than denials: each buy is
checked alone against free cash, so two buys that each fit but jointly do
not both pass, the fills drive cash negative, and the engine *stops the whole
backtest* with ``AccountBalanceNegative``.  With bars only (no trade prices)
the RiskEngine cannot check market orders at all ("Cannot check MARKET order
risk: no prices"), and buys-first halts the backtest on the first rebalance
that needs sells to fund buys.

On the full 8-name 2016-2022 HRP run (``python -m quantstack.execution.backtest``):
two_phase 573 orders / 573 fills / 0 denied; sells_first 571 / 551 / 20 denied
(completes, but drifts off target); buys_first halts on the second rebalance
(2017-02-01) with ``AccountBalanceNegative(balance=-729.97)``.

So the default ``order_mode="two_phase"`` submits the sells, waits for every
sell to reach a terminal state (filled / denied / rejected / canceled), and
only then submits the buys.  The venue drains its command queue until empty,
so the buys still fill at the same close in the backtest; live, they would go
out as soon as the sells are done, which is how a real cash-account
rebalance must be sequenced.  ``sells_first`` and ``buys_first`` are kept
only to reproduce the table above.

Equity (which Nautilus API and why)
-----------------------------------
``equity = account.balance_total(USD) + sum(net_position * last_close)``
where the account comes from ``self.portfolio.account(venue)`` (a
``CashAccount``: its total balance *is* the cash; stock purchases debit it)
and quantities from ``self.portfolio.net_position(instrument_id)``
(a ``Decimal``, 0 when flat).  We price with the bar closes the strategy
already holds rather than trusting ``Portfolio.equity(venue)`` blindly
(that one depends on which price source the portfolio has cached, and warns
and *drops* unpriced instruments); both are computed once all of a day's bars
are in, and the largest absolute difference is kept in
``self.max_equity_check_diff`` as a cross-check (``self.n_equity_checks``
counts the days the comparison actually ran, so a zero difference cannot come
from a check that never happened).  The check has no exception handler: a
failure there is a bug to surface, not a diagnostic to hide.

Fill assumption (optimistic market-on-close)
--------------------------------------------
Weights are sized on a day's closes and the orders fill at that same close:
the strategy sees the close, then trades at it.  With close-only bars and the
default fill model that is what the simulated venue does.  It is the
article's simplification, and an optimistic one: a live strategy would size
on an estimate before the close and submit market-on-close orders, or trade
the next day.

When the book is published (fill timing)
----------------------------------------
Fills land after ``on_bar`` returns, so inside ``on_bar`` on a rebalance day
the positions are still pre-trade.  Equity does not care (fills at the close
without costs leave cash + market value unchanged), but the positions rows
would lag by a day.  So each day's batch is published as an end-of-day
snapshot: when the first bar of the *next* day arrives (all of today's fills
are booked by then), or from ``on_stop`` for the final day.  Values are marked
at the closes of the day they are labelled with.

Allocators
----------
``"hrp"``: ``skfolio.optimization.HierarchicalRiskParity()`` with its
defaults, fitted through ``contracts.fit_weights`` (the contract, not
``quantstack.allocation``, which is built concurrently).  ``"equal"``: 1/N.
``"fixed"``: a caller-supplied constant vector (``fixed_weights``, symbol ->
weight) naming exactly the traded universe, rescaled to sum to 1 (see
:func:`normalise_fixed_weights`), so the book is pulled back to the same
target at every rebalance.  All run on the same schedule (first rebalance
once warmed up, then every ``rebalance_every`` days), so a comparison
isolates the weighting scheme.
"""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timezone
from decimal import Decimal

import numpy as np
import pandas as pd

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.events import (
    OrderCanceled,
    OrderDenied,
    OrderExpired,
    OrderFilled,
    OrderRejected,
)
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.trading.strategy import Strategy

from quantstack.contracts import (
    DashboardSink,
    NullSink,
    OrderIntent,
    Position,
    PositionSnapshot,
    fit_weights,
    target_deltas,
    validate_weights,
)

ALLOCATORS = ("hrp", "equal", "fixed")
ORDER_MODES = ("two_phase", "sells_first", "buys_first")


class SkfolioRebalanceConfig(StrategyConfig, frozen=True):
    """Configuration for :class:`SkfolioRebalance`.

    ``instrument_ids`` and ``bar_types`` are parallel lists (one daily bar
    type per instrument).  ``investment_cap`` is the fraction of equity
    deployed; the remaining cash buffer absorbs rounding and price drift.
    ``order_mode`` is ``"two_phase"`` for real runs; the other two modes exist
    to reproduce the failure modes documented in the module docstring.
    ``fixed_weights`` (symbol -> weight, keyed like ``InstrumentId.symbol``,
    e.g. ``"AAPL"``) is required with ``allocator="fixed"`` and must be
    ``None`` otherwise; see :func:`check_fixed_weights`.
    """

    instrument_ids: list[InstrumentId]
    bar_types: list[BarType]
    lookback_bars: int = 252
    rebalance_every: int = 21
    investment_cap: float = 0.98
    allocator: str = "hrp"
    order_mode: str = "two_phase"
    fixed_weights: dict[str, float] | None = None


def check_fixed_weights(
    allocator: str,
    fixed_weights: Mapping[str, float] | None,
    symbols: Iterable[str] | None = None,
) -> None:
    """Raise ``ValueError`` unless ``fixed_weights`` fits ``allocator`` (and the universe).

    ``allocator="fixed"`` needs a non-empty mapping symbol -> weight whose
    values are finite and non-negative; any other allocator needs ``None``.
    With ``symbols`` (the universe) it also runs
    :func:`normalise_fixed_weights`, so a universe symbol without a weight, a
    weight for a symbol outside the universe, or weights summing to zero fail
    here rather than at the first rebalance.
    """
    if allocator != "fixed":
        if fixed_weights is not None:
            raise ValueError(f"fixed_weights is only used with allocator='fixed', got allocator={allocator!r}")
        return
    if not isinstance(fixed_weights, Mapping) or not fixed_weights:
        raise ValueError("allocator='fixed' needs fixed_weights: a non-empty mapping symbol -> weight, "
                         f"got {fixed_weights!r}")
    for symbol, w in fixed_weights.items():
        try:
            w = float(w)
        except (TypeError, ValueError):
            raise ValueError(f"fixed weight for {symbol!r} is not a number: {w!r}") from None
        if not math.isfinite(w) or w < 0:
            raise ValueError(f"fixed weight for {symbol!r} must be finite and >= 0, got {w}")
    if symbols is not None:
        normalise_fixed_weights(fixed_weights, symbols)


def normalise_fixed_weights(fixed_weights: Mapping[str, float], symbols: Iterable[str]) -> dict[str, float]:
    """``fixed_weights`` over ``symbols``, rescaled to sum to 1, as validated ``Weights`` (in ``symbols`` order).

    Fixed weights are relative: ``{"A": 2, "B": 1, "C": 1}`` and
    ``{"A": 0.5, "B": 0.25, "C": 0.25}`` both mean 50/25/25 (the investment
    cap then applies as for every allocator).  The keys must be exactly the
    universe: every symbol needs a weight (0 to hold none) and a weight for a
    symbol that is not traded is refused rather than silently dropped (the
    rest would be rescaled around the hole).  Either mismatch raises
    ``ValueError`` listing the missing and the extra symbols, as does a zero
    total.
    """
    symbols = [str(s) for s in symbols]
    universe = set(symbols)
    missing = [s for s in symbols if s not in fixed_weights]
    extra = sorted(str(k) for k in fixed_weights if str(k) not in universe)
    if missing or extra:
        problems = []
        if missing:
            problems.append(f"no weight for {missing} (every symbol needs one, 0 to hold none)")
        if extra:
            problems.append(f"weights for {extra}, which are not in the universe")
        raise ValueError(f"fixed_weights must name exactly the universe {symbols}: " + "; ".join(problems))
    raw = {s: float(fixed_weights[s]) for s in symbols}
    total = sum(raw.values())
    if not total > 0:
        raise ValueError(f"fixed weights over {symbols} sum to {total}; need a positive total")
    return validate_weights({s: w / total for s, w in raw.items()})


def window_returns(prices: pd.DataFrame, label: str = "") -> pd.DataFrame:
    """Simple returns of a trailing price window, guaranteed finite, or ``ValueError``.

    ``pct_change`` (no forward fill) with its first row (always NaN) dropped,
    ``+-inf`` (a zero close followed by a non-zero one) mapped to NaN.  If any
    NaN is left -- from a zero, negative, NaN or infinite close -- the window
    is refused with a ``ValueError`` naming each such symbol and its number of
    bad returns, instead of silently dropping those days or letting the
    allocator choke on them (skfolio raised "Input X contains infinity" from
    inside ``engine.run()``).  ``data.make_bars`` already refuses closes that
    are not positive after rounding, so in the backtest this is a last line of
    defence.  For a finite, positive window the result is exactly
    ``prices.pct_change().dropna()``.
    """
    rets = prices.astype(float).pct_change(fill_method=None).iloc[1:]
    rets = rets.replace([np.inf, -np.inf], np.nan)
    bad = rets.isna().sum()
    bad = bad[bad > 0]
    if len(bad) or rets.empty:
        where = f"{label}: " if label else ""
        detail = ", ".join(f"{s} ({int(n)} of {len(prices) - 1})" for s, n in bad.items()) or "every symbol"
        raise ValueError(f"{where}non-finite returns in the {len(prices)}-bar price window for {detail}: "
                         "a zero, negative or non-finite close; refusing to size the book on it")
    return rets


def _ns_to_date(ts_ns: int) -> date:
    return datetime.fromtimestamp(ts_ns / 1e9, tz=timezone.utc).date()


def _ns_to_iso(ts_ns: int) -> str:
    return pd.Timestamp(ts_ns, unit="ns", tz="UTC").isoformat()


class SkfolioRebalance(Strategy):
    """Periodic long-only rebalance to skfolio weights on a cash account.

    ``sink`` is any :class:`quantstack.contracts.DashboardSink` (the
    Perspective adapter in production, ``RecordingSink`` in tests).  It is a
    constructor argument rather than a config field because Nautilus configs
    must be serialisable.
    """

    def __init__(self, config: SkfolioRebalanceConfig, sink: DashboardSink | None = None) -> None:
        super().__init__(config)
        if config.allocator not in ALLOCATORS:
            raise ValueError(f"allocator must be one of {ALLOCATORS}, got {config.allocator!r}")
        if config.order_mode not in ORDER_MODES:
            raise ValueError(f"order_mode must be one of {ORDER_MODES}, got {config.order_mode!r}")
        if len(config.instrument_ids) != len(config.bar_types):
            raise ValueError("instrument_ids and bar_types must be parallel lists")
        if config.lookback_bars < 3 or config.rebalance_every < 1:
            raise ValueError("lookback_bars must be >= 3 and rebalance_every >= 1")
        self.sink: DashboardSink = sink if sink is not None else NullSink()
        self.symbols: list[str] = [iid.symbol.value for iid in config.instrument_ids]
        check_fixed_weights(config.allocator, config.fixed_weights, self.symbols)
        self.ids: dict[str, InstrumentId] = {iid.symbol.value: iid for iid in config.instrument_ids}
        self.venue = config.instrument_ids[0].venue
        self.closes: dict[str, deque] = {s: deque(maxlen=config.lookback_bars) for s in self.symbols}
        self.last: dict[str, float] = {}
        self.instruments: dict = {}

        # day bookkeeping
        self._day_ts: int | None = None
        self._seen_today: set[str] = set()
        self.days_completed = 0
        self._days_since_rebalance: int | None = None

        # two-phase order state
        self._open_sells: set[str] = set()
        self._pending_buys: list[OrderIntent] = []
        self._pending_day: str = ""
        self._submitting = False

        # diagnostics / outputs read by backtest.py and the tests
        self.rebalance_dates: list[date] = []
        self.weights_history: list[dict] = []    # target weights per rebalance: {"date", <symbol>: w}
        self.achieved_history: list[dict] = []   # the book right after that rebalance's fills, same keys
        self._achieved_due: str | None = None    # ISO date of a rebalance whose achieved row is pending
        self.submitted: list[dict] = []          # every submitted order, in submission order
        self.fills: list[dict] = []
        self.n_fills = 0
        self.n_rejected = 0
        self.n_denied = 0
        self.n_canceled = 0
        self.rejections: list[str] = []
        self.fit_seconds: list[float] = []
        self.max_equity_check_diff = 0.0
        self.n_equity_checks = 0
        self.published_days = 0
        self.last_snapshot: PositionSnapshot | None = None

    # ------------------------------------------------------------------ lifecycle
    def on_start(self) -> None:
        for s, iid in self.ids.items():
            inst = self.cache.instrument(iid)
            if inst is None:
                self.log.error(f"instrument {iid} not in cache; stopping")
                self.stop()
                return
            self.instruments[s] = inst
        for bt in self.config.bar_types:
            self.subscribe_bars(bt)

    def on_stop(self) -> None:
        # Final end-of-day snapshot; the last day's fills are booked by now.
        if self._day_ts is not None and self._seen_today:
            self._publish_day(self._day_ts)
            self._day_ts = None

    # ------------------------------------------------------------------ data
    def on_bar(self, bar: Bar) -> None:
        sym = bar.bar_type.instrument_id.symbol.value
        if sym not in self.closes:
            return
        ts = bar.ts_event
        if self._day_ts is None or ts > self._day_ts:
            # New session: yesterday is complete and its fills are booked.
            if self._day_ts is not None:
                self._publish_day(self._day_ts)
            self._day_ts = ts
            self._seen_today = set()
        close = float(bar.close)
        self.closes[sym].append(close)
        self.last[sym] = close
        self._seen_today.add(sym)
        if len(self._seen_today) == len(self.symbols):
            self._on_day_complete(ts)

    def _on_day_complete(self, ts: int) -> None:
        """All symbols have today's close: cross-check equity, maybe rebalance."""
        self.days_completed += 1
        self._check_equity()
        warmed = all(len(self.closes[s]) >= self.config.lookback_bars for s in self.symbols)
        if not warmed:
            return
        if self._days_since_rebalance is None or self._days_since_rebalance >= self.config.rebalance_every:
            self._rebalance(ts)
            self._days_since_rebalance = 1
        else:
            self._days_since_rebalance += 1

    # ------------------------------------------------------------------ book
    def current_qtys(self) -> dict[str, float]:
        return {s: float(self.portfolio.net_position(iid)) for s, iid in self.ids.items()}

    def cash(self) -> float:
        account = self.portfolio.account(self.venue)
        if account is None:
            return 0.0
        bal = account.balance_total(USD)
        return float(bal.as_double()) if bal is not None else 0.0

    def equity(self) -> float:
        qtys = self.current_qtys()
        return self.cash() + sum(q * self.last.get(s, 0.0) for s, q in qtys.items())

    def _check_equity(self) -> None:
        """Compare :meth:`equity` with ``Portfolio.equity(venue)`` and keep the worst gap.

        ``Portfolio.equity`` returns ``{}`` until the venue's account exists;
        that day is skipped (not counted).  Anything else that goes wrong
        raises: no broad ``except`` here.
        """
        nt = self.portfolio.equity(self.venue).get(USD)
        if nt is None:
            return
        diff = abs(nt.as_double() - self.equity())
        self.max_equity_check_diff = max(self.max_equity_check_diff, diff)
        self.n_equity_checks += 1

    def snapshot(self, as_of: date) -> PositionSnapshot:
        qtys = self.current_qtys()
        positions = [Position(s, qtys[s], self.last.get(s, float("nan"))) for s in self.symbols]
        return PositionSnapshot(as_of=as_of, positions=positions, cash=self.cash())

    def _publish_day(self, day_ts: int) -> None:
        day = _ns_to_date(day_ts)
        snap = self.snapshot(day)
        self.last_snapshot = snap
        if self._achieved_due == day.isoformat():
            self._record_achieved(snap)
        # one batched call per table per day
        self.sink.update_positions(snap.to_rows())
        self.sink.update_equity([{"date": day.isoformat(), "equity": snap.equity}])
        self.published_days += 1

    def _record_achieved(self, snap: PositionSnapshot) -> None:
        """Achieved weights after a rebalance: ``qty * close / equity`` per symbol.

        Called from the end-of-day publish of the rebalance day, when every
        fill of that rebalance is booked, marked at that day's closes (the
        prices the orders were sized and filled at).  Fractions of equity, so
        they sum to at most ``investment_cap`` plus drift, like the orders'
        own target ``investment_cap * weight``.
        """
        eq = snap.equity
        row: dict = {"date": self._achieved_due}
        for p in snap.positions:
            row[p.symbol] = (p.qty * p.last / eq) if eq > 0 else float("nan")
        self.achieved_history.append(row)
        self._achieved_due = None

    # ------------------------------------------------------------------ sizing
    def price_frame(self) -> pd.DataFrame:
        n = min(len(self.closes[s]) for s in self.symbols)
        return pd.DataFrame({s: list(self.closes[s])[-n:] for s in self.symbols})

    def compute_weights(self, returns: pd.DataFrame) -> dict[str, float]:
        if self.config.allocator == "equal":
            n = returns.shape[1]
            return validate_weights({s: 1.0 / n for s in returns.columns})
        if self.config.allocator == "fixed":
            return normalise_fixed_weights(self.config.fixed_weights, returns.columns)
        from skfolio.optimization import HierarchicalRiskParity

        return fit_weights(HierarchicalRiskParity(), returns)

    def _rebalance(self, ts: int) -> None:
        day = _ns_to_date(ts).isoformat()
        if self._open_sells or self._pending_buys:
            self.log.warning(f"{day}: previous rebalance still in flight; skipping")
            return
        returns = window_returns(self.price_frame(), label=f"rebalance {day}")
        t0 = time.perf_counter()
        weights = self.compute_weights(returns)
        self.fit_seconds.append(time.perf_counter() - t0)
        self.rebalance_dates.append(_ns_to_date(ts))
        self.weights_history.append({"date": day, **weights})
        self._achieved_due = day

        intents = target_deltas(
            weights,
            equity=self.equity(),
            prices=dict(self.last),
            positions=self.current_qtys(),
            investment_cap=self.config.investment_cap,
        )
        mode = self.config.order_mode
        if mode == "buys_first":
            self._submit_all(sorted(intents, key=lambda o: -o.delta_qty), day)
        elif mode == "sells_first":
            self._submit_all(intents, day)  # target_deltas already sorts sells first
        else:  # two_phase
            sells = [o for o in intents if o.delta_qty < 0]
            self._pending_buys = [o for o in intents if o.delta_qty > 0]
            self._pending_day = day
            self._submitting = True
            try:
                for o in sells:
                    order = self._submit_intent(o, day)
                    if order is not None and not order.is_closed:
                        self._open_sells.add(order.client_order_id.value)
            finally:
                self._submitting = False
            self._maybe_release_buys()

    def _submit_all(self, intents: list[OrderIntent], day: str) -> None:
        for o in intents:
            self._submit_intent(o, day)

    def _submit_intent(self, intent: OrderIntent, day: str):
        inst = self.instruments[intent.symbol]
        qty = inst.make_qty(Decimal(abs(int(round(intent.delta_qty)))))
        if qty.as_double() <= 0:
            return None
        side = OrderSide.BUY if intent.delta_qty > 0 else OrderSide.SELL
        order = self.order_factory.market(instrument_id=inst.id, order_side=side, quantity=qty)
        self.submitted.append(
            {"date": day, "symbol": intent.symbol, "side": intent.side,
             "qty": qty.as_double(), "client_order_id": order.client_order_id.value}
        )
        self.submit_order(order)
        return order

    def _maybe_release_buys(self) -> None:
        """Phase two: once every sell of this rebalance is terminal, send the buys."""
        if self._submitting or self._open_sells or not self._pending_buys:
            return
        buys, self._pending_buys = self._pending_buys, []
        self._submit_all(buys, self._pending_day)

    def _sell_done(self, client_order_id: str) -> None:
        if client_order_id in self._open_sells:
            self._open_sells.discard(client_order_id)
            self._maybe_release_buys()

    # ------------------------------------------------------------------ events
    def on_order_filled(self, event: OrderFilled) -> None:
        self.n_fills += 1
        row = {
            "ts": _ns_to_iso(event.ts_event),
            "symbol": event.instrument_id.symbol.value,
            "side": "BUY" if event.order_side == OrderSide.BUY else "SELL",
            "qty": float(event.last_qty),
            "price": float(event.last_px),
        }
        self.fills.append(row)
        self.sink.update_fills([row])
        coid = event.client_order_id.value
        if coid in self._open_sells:
            order = self.cache.order(event.client_order_id)
            if order is None or order.is_closed:
                self._sell_done(coid)

    def on_order_rejected(self, event: OrderRejected) -> None:
        self.n_rejected += 1
        self.rejections.append(f"REJECTED {event.client_order_id}: {event.reason}")
        self.log.warning(f"order rejected: {event.client_order_id} {event.reason}")
        self._sell_done(event.client_order_id.value)

    def on_order_denied(self, event: OrderDenied) -> None:
        self.n_denied += 1
        self.rejections.append(f"DENIED {event.client_order_id}: {event.reason}")
        self.log.warning(f"order denied: {event.client_order_id} {event.reason}")
        self._sell_done(event.client_order_id.value)

    def on_order_canceled(self, event: OrderCanceled) -> None:
        self.n_canceled += 1
        self._sell_done(event.client_order_id.value)

    def on_order_expired(self, event: OrderExpired) -> None:
        self.n_canceled += 1
        self._sell_done(event.client_order_id.value)


__all__ = ["SkfolioRebalance", "SkfolioRebalanceConfig", "ALLOCATORS", "ORDER_MODES",
           "check_fixed_weights", "normalise_fixed_weights", "window_returns"]
