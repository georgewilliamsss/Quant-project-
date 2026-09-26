"""The "positions -> risk" wire: a positions snapshot as an ORE portfolio file.

Why a file, and why this shape
------------------------------
Contract 3 in :mod:`quantstack.contracts` says the risk engine reads a book that
*another program* (the execution engine) wrote - the industry separates the two
on purpose, so that nobody marks their own homework.  NautilusTrader's side of
that wire is ``contracts.write_positions_csv``; this module is ORE's side: it
turns a :class:`~quantstack.contracts.PositionSnapshot` (or that CSV) into an ORE
``<Portfolio>`` XML, which is the only way ORE takes trades in.

Each position becomes one ``<Trade>`` of ``TradeType`` ``EquityPosition``, the
ORE product for "N units of a listed equity" (schema from ORE v1.8.16.0
``Examples/Products/Input/referencedata.xml`` and
``OREData/ored/portfolio/equityposition.hpp``)::

    <Trade id="EQ_AAPL">
      <TradeType>EquityPosition</TradeType>
      <Envelope>
        <CounterParty>CPTY_A</CounterParty>
        <NettingSetId>CPTY_A</NettingSetId>
        <AdditionalFields> as_of, currency, last_price, market_value, symbol </AdditionalFields>
      </Envelope>
      <EquityPositionData>
        <Quantity>100</Quantity>
        <Underlying><Type>Equity</Type><Name>AAPL</Name><Weight>1</Weight></Underlying>
      </EquityPositionData>
    </Trade>

Notes from checking this against ORE 1.8.17.0 itself (see the tests):

* ``ORE.Portfolio().fromXMLString(xml)`` parses the result; ``size()`` equals the
  number of positions and every ``tradeType()`` is ``EquityPosition``.
* ``<Underlying>`` has no currency element - ORE silently drops a
  ``<Currency>`` there (the equity's currency comes from the equity curve config
  in ORE's market).  The execution engine's currency and last price are
  therefore carried in ``Envelope/AdditionalFields``, which ORE round-trips
  verbatim and exposes to reports; ORE never uses them for pricing.
* ``<Weight>1</Weight>`` is written explicitly because it is what ORE writes
  back (``toXMLString``) for a single-underlying position.

What this is *not*: this equity book is **not priced** by the 2016-02-05 EUR demo
market in ``quantstack/risk/input`` - that market has no equity spot/curve for
arbitrary US tickers.  Feeding it to that run makes ORE refuse every trade with
``did not find object 'SPY' of type equity curve under configuration 'libor' or
'default'`` (and :func:`quantstack.risk.run_ore.run_exposure` turns the resulting
missing ``npv`` report into an ``OreRunError``; there is a test for exactly this).  Pricing it needs an equity market (``EquityCurves`` in
todaysmarket/curveconfig plus ``EQUITY/PRICE/<name>/<ccy>`` quotes).  The wire
delivered here is the *file contract* and ORE's parser accepting it.
"""

from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from quantstack.contracts import Position, PositionSnapshot, read_positions_csv

MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parents[1]

_ID_SAFE = re.compile(r"[^A-Za-z0-9_.\-]")


def trade_id_for(symbol: str, prefix: str = "EQ_") -> str:
    """Deterministic ORE trade id for a symbol (``BRK/B`` -> ``EQ_BRK_B``)."""
    return prefix + _ID_SAFE.sub("_", symbol.strip())


def _fmt(x: float) -> str:
    # repr() is the shortest string that round-trips a float exactly.
    x = float(x)
    return str(int(x)) if x.is_integer() and abs(x) < 1e15 else repr(x)


def positions_to_ore_portfolio_xml(
    snapshot: PositionSnapshot,
    counterparty: str = "CPTY_A",
    netting_set: str = "CPTY_A",
    currency: str = "USD",
    *,
    drop_flat: bool = False,
) -> str:
    """Render ``snapshot`` as an ORE ``<Portfolio>`` XML string.

    One ``EquityPosition`` trade per position (``drop_flat=True`` skips zero
    quantities).  Trade ids are ``EQ_<symbol>``; two positions mapping to the same
    id raise ``ValueError`` rather than letting ORE keep only one of them.
    Quantities keep their sign (a short is a negative ``Quantity``).
    """
    root = ET.Element("Portfolio")
    seen: set[str] = set()
    for pos in snapshot.positions:
        if drop_flat and float(pos.qty) == 0.0:
            continue
        tid = trade_id_for(pos.symbol)
        if tid in seen:
            raise ValueError(f"duplicate trade id {tid!r} (symbol {pos.symbol!r}); aggregate first")
        seen.add(tid)

        trade = ET.SubElement(root, "Trade", {"id": tid})
        ET.SubElement(trade, "TradeType").text = "EquityPosition"
        env = ET.SubElement(trade, "Envelope")
        ET.SubElement(env, "CounterParty").text = counterparty
        ET.SubElement(env, "NettingSetId").text = netting_set
        extra = ET.SubElement(env, "AdditionalFields")
        ET.SubElement(extra, "as_of").text = snapshot.as_of.isoformat()
        ET.SubElement(extra, "symbol").text = pos.symbol
        ET.SubElement(extra, "currency").text = currency
        ET.SubElement(extra, "last_price").text = _fmt(pos.last)
        ET.SubElement(extra, "market_value").text = _fmt(pos.value)

        data = ET.SubElement(trade, "EquityPositionData")
        ET.SubElement(data, "Quantity").text = _fmt(pos.qty)
        und = ET.SubElement(data, "Underlying")
        ET.SubElement(und, "Type").text = "Equity"
        ET.SubElement(und, "Name").text = pos.symbol
        ET.SubElement(und, "Weight").text = "1"

    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def write_ore_portfolio(snapshot: PositionSnapshot, path: str | Path, **kwargs) -> Path:
    """Write :func:`positions_to_ore_portfolio_xml` to ``path`` (parents created)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(positions_to_ore_portfolio_xml(snapshot, **kwargs))
    return path


def positions_csv_to_ore_portfolio(csv_path: str | Path, xml_path: str | Path, **kwargs) -> Path:
    """The full cross-process hop: execution's positions CSV -> ORE portfolio XML."""
    return write_ore_portfolio(read_positions_csv(csv_path), xml_path, **kwargs)


def parse_with_ore(xml: str | None = None, path: str | Path | None = None) -> list[tuple[str, str]]:
    """Let ORE itself parse a portfolio; return ``[(trade id, trade type), ...]``.

    Uses ``ORE.Portfolio.fromXMLString`` / ``fromFile`` (ORE 1.8.17.0 has both).
    Parsing does not build (price) the trades, so no market is needed.
    """
    import ORE

    if (xml is None) == (path is None):
        raise ValueError("pass exactly one of xml= or path=")
    pf = ORE.Portfolio()
    if xml is not None:
        pf.fromXMLString(xml)
    else:
        pf.fromFile(str(path))
    return [(tid, pf.get(tid).tradeType()) for tid in pf.ids()]


def demo_snapshot() -> PositionSnapshot:
    """A small book shaped like the execution module's output (for the CLI/tests)."""
    return PositionSnapshot(
        as_of=date(2024, 12, 31),
        positions=[
            Position("SPY", 120.0, 586.08),
            Position("QQQ", 45.0, 511.23),
            Position("TLT", 200.0, 86.94),
            Position("GLD", 60.0, 242.13),
        ],
        cash=12_345.67,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m quantstack.risk.portfolio_writer",
        description="Turn a positions CSV (contracts.write_positions_csv) into an ORE portfolio XML.",
    )
    ap.add_argument("--positions", default=None, help="positions CSV; default: a demo snapshot")
    ap.add_argument("--out", default=str(REPO_ROOT / "results" / "ore_output" / "portfolio_equity.xml"))
    ap.add_argument("--counterparty", default="CPTY_A")
    ap.add_argument("--netting-set", default="CPTY_A")
    ap.add_argument("--currency", default="USD")
    args = ap.parse_args(argv)
    snap = read_positions_csv(args.positions) if args.positions else demo_snapshot()
    path = write_ore_portfolio(snap, args.out, counterparty=args.counterparty,
                               netting_set=args.netting_set, currency=args.currency)
    trades = parse_with_ore(path=path)
    print(f"wrote {path} with {len(trades)} trades; ORE parsed: "
          + ", ".join(f"{tid}:{tt}" for tid, tt in trades))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
