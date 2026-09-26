"""``quantstack.dashboard`` -- the display layer: State -> Screen (contract 4).

This module wires ``contracts.DashboardSink`` up to a real Perspective server
(perspective-python 5.5.1) plus a Tornado websocket handler, and serves the
``<perspective-viewer>`` page that renders it.  The point of the exercise
(per the article "Five Repos, One Engine") is that this is the *one* wire in
the whole stack you can actually watch on a network tab: bytes really cross a
loopback socket between the Python ``Table`` and the browser (or, in our
test, a second in-process Python client standing in for the browser).

SECURITY WARNING -- READ BEFORE DEPLOYING
==========================================
``perspective.handlers.tornado.PerspectiveTornadoHandler`` is, in its own
docstring, described as "a reference integration with **no authentication,
authorization, origin enforcement, or rate limiting**, and is not safe to
expose to untrusted networks."  Anyone who can open a websocket to ``/ws``
can read *and write* every table this process hosts.  Because of this:

* :func:`serve` and the CLI both default ``--host`` to ``127.0.0.1``
  (loopback only).
* Binding to ``0.0.0.0`` (or any non-loopback address) requires passing
  ``--host 0.0.0.0`` explicitly -- there is no way to do it by accident.
* Do not put this behind a reverse proxy on a shared network without adding
  your own auth layer in front of it.

Version-skew notes (perspective-python 5.5.1, Sept 2026)
==========================================================
1. npm package renames.  Most docs and examples on the web still say
   "npm install @finos/perspective".  As of this pinned version the upstream
   project (now developed at github.com/perspective-dev/perspective, still
   published to PyPI as ``perspective-python``) renamed its JS packages:

       @finos/perspective                 -> @perspective-dev/client
       @finos/perspective-viewer          -> @perspective-dev/viewer
       @finos/perspective-viewer-datagrid -> @perspective-dev/viewer-datagrid
       @finos/perspective-viewer-d3fc     -> @perspective-dev/viewer-charts   (renamed, not just scoped)

   This was *not* guessed: it is read directly out of the installed
   package's own ``perspective/widget/__init__.py`` (the Jupyter "export as
   HTML" code path), which builds exactly these jsdelivr URLs, version-pinned
   via ``perspective.__version__``:

       https://cdn.jsdelivr.net/npm/@perspective-dev/client@5.5.1/dist/cdn/perspective.js
       https://cdn.jsdelivr.net/npm/@perspective-dev/viewer@5.5.1/dist/cdn/perspective-viewer.js
       https://cdn.jsdelivr.net/npm/@perspective-dev/viewer-datagrid@5.5.1/dist/cdn/perspective-viewer-datagrid.js
       https://cdn.jsdelivr.net/npm/@perspective-dev/viewer-charts@5.5.1/dist/cdn/perspective-viewer-charts.js

   ``static/index.html`` in this package uses these exact URLs.

2. The JS client needs the *viewer* to have registered first.  The call
   *names* (``await perspective.websocket(url)``, then tables by name) match
   the docstring of ``PerspectiveTornadoHandler``, but in 5.5.1
   ``perspective.websocket()`` no longer ships its own client wasm: it takes
   the compiled ``perspective-client.wasm`` from the registered
   ``<perspective-viewer>`` custom element, and the viewer's CDN module only
   registers that element after a top-level ``await`` on its own wasm.  A
   page that calls ``websocket()`` straight away therefore fails in a real
   browser with ``Error: Missing perspective-client.wasm``.  The fix, which
   the installed package's own ``perspective/templates/
   exported_widget.html.template`` uses (with a comment saying why), is
   ``await customElements.whenDefined("perspective-viewer")`` before creating
   the client.  ``static/index.html`` does exactly that.  Checked in the
   pre-installed Chromium 1194 (headless, driven over the DevTools protocol
   -- playwright's Python package is not installed and was not added):
   without the wait the page shows ``connection failed: Error: Missing
   perspective-client.wasm``; with it both viewers render the replayed
   tables (``results/figures/dashboard_screenshot.png``; for that check the
   jsdelivr prefix was pointed at the identical 5.5.1 npm tarballs served
   locally, nothing else in the page changed).

3. ``viewer.load(table)`` is deprecated in viewer 5.5.1 (it logs a warning);
   the supported form is ``viewer.load(client)`` followed by
   ``viewer.restore({table: "<name>", ...})``, which ``static/index.html``
   uses.

4. Python-side update path.  ``Table.update(list_of_dicts)`` goes through
   Perspective's JSON ingestion, which in 5.5.1 (a) silently drops the
   *whole batch* if any value is NaN or +/-inf (no exception -- the table is
   simply unchanged), (b) re-parses floats with ~1 ulp of drift
   (``98.27639451941653`` comes back as ``98.27639451941651``), and (c)
   raises ``TypeError: not JSON serializable`` on ``np.int64``,
   ``np.float32`` or ``datetime.date`` values that ``RecordingSink``
   happily accepts.  :class:`PerspectiveSink` therefore builds a typed Apache
   Arrow batch itself (``float`` columns via ``float(v)``, the same coercion
   ``RecordingSink.update_equity`` applies; ``string`` columns via
   ``isoformat()``/``str()``) and hands Perspective Arrow IPC bytes, one of
   its documented input formats.  That path is bit-exact, maps NaN to null
   instead of losing the batch, and stores +/-inf as-is (note: JSON *reads*
   such as ``view.to_records()`` then show inf as ``None``; ``to_arrow()``
   still returns inf).

Another skew worth flagging: the "websocket client" most tutorials point to
(the pure-Python ``websocket-client`` package, used in perspective's own
``tests/async/test_websocket_client.py``) is not installed here and we were
told not to pip-install new packages without good reason. Tornado itself
ships an async websocket client (``tornado.websocket.websocket_connect``),
so :mod:`tests.test_dashboard` and :func:`run_wire_selftest` use that
instead, paired with ``perspective.AsyncClient`` (see
``perspective/tests/async/test_async_client.py`` in the installed package for
the reference pattern this follows: a client-side coroutine gives
``AsyncClient`` a ``handle_request`` callback that writes bytes out, and
feeds incoming bytes back in via ``AsyncClient.handle_response`` scheduled on
the *client's* event loop). No new dependency was needed.

One sink per ``perspective.Server``: table names are global to a server, so a
second :class:`PerspectiveSink` on the same server would collide on
``"positions"``; the constructor refuses that up front with a clear
``ValueError`` rather than Perspective's ``Abort(): Table "positions" already
exists``.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import json
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd
import perspective
import pyarrow as pa
import tornado.httpserver
import tornado.ioloop
import tornado.netutil
import tornado.web
from perspective.handlers.tornado import PerspectiveTornadoHandler

from quantstack.contracts import (
    EQUITY_SCHEMA,
    FILLS_SCHEMA,
    POSITIONS_SCHEMA,
    read_positions_csv,
)

STATIC_DIR = Path(__file__).parent / "static"
RESULTS_DIR = Path(__file__).resolve().parents[2] / "results"
DEFAULT_EQUITY_CSV = RESULTS_DIR / "execution_equity.csv"
DEFAULT_POSITIONS_CSV = RESULTS_DIR / "execution_positions.csv"
DEFAULT_FILLS_CSV = RESULTS_DIR / "execution_fills.csv"
FILLS_CSV_NAME = DEFAULT_FILLS_CSV.name
TABLE_NAMES = ("positions", "equity", "fills")

# Tornado's default cap on an *incoming* websocket message is 10 MiB. Browser
# requests are tiny, but a client that uploads a table (the handler lets any
# client write -- see the security warning) or a future bulk replay would hit
# it, and perspective's handler docstring warns about large datasets. 64 MiB
# is ample for this project's data (1760 equity rows, 573 fills).
DEFAULT_WEBSOCKET_MAX_MESSAGE_SIZE = 64 * 1024 * 1024


# --------------------------------------------------------------------------
# Row -> Arrow conversion (see module docstring, version-skew note 4)
# --------------------------------------------------------------------------


def _is_missing(value) -> bool:
    """True for None / NaN / NaT / pd.NA scalars; False for everything else
    (including containers, for which ``pd.isna`` returns an array)."""
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _coerce_float(value) -> float | None:
    # float(v): same coercion RecordingSink.update_equity applies, and it
    # accepts np.int64/np.float32/Decimal/... that the JSON path rejects.
    return None if _is_missing(value) else float(value)


def _coerce_string(value) -> str | None:
    if _is_missing(value):
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, _dt.date):  # date, datetime, pd.Timestamp
        return value.isoformat()
    return str(value)


_COERCERS = {
    "float": (_coerce_float, pa.float64()),
    "string": (_coerce_string, pa.string()),
}


def _rows_to_arrow_ipc(
    rows: list[Mapping], schema: Mapping[str, str], index: str | None
) -> bytes:
    """Encode ``rows`` as an Arrow IPC stream typed by ``schema``.

    * Only schema columns are sent (the screen has no column for anything
      else).  A schema column that *no* row mentions is left out entirely, so
      an indexed update that only carries e.g. ``qty`` keeps the other cells
      (Perspective's partial-update semantics).
    * A missing value (key absent in that row, None, NaN) becomes null --
      never a silently dropped batch.
    * Indexed tables require the index key on every row, mirroring
      ``RecordingSink`` (which raises ``KeyError`` on ``r["symbol"]``).
    """
    if index is not None:
        for r in rows:
            if index not in r:
                raise KeyError(index)
    columns = [c for c in schema if any(c in r for r in rows)]
    if not columns:
        raise ValueError(
            f"none of the rows carry any schema column {list(schema)}; "
            f"got keys {sorted({k for r in rows for k in r})}"
        )
    arrays, fields = [], []
    for col in columns:
        try:
            coerce, arrow_type = _COERCERS[schema[col]]
        except KeyError:  # contracts only uses float/string today
            raise ValueError(f"unsupported schema type {schema[col]!r} for {col!r}")
        arrays.append(pa.array([coerce(r.get(col)) for r in rows], type=arrow_type))
        fields.append(pa.field(col, arrow_type))
    batch = pa.Table.from_arrays(arrays, schema=pa.schema(fields))
    out = pa.BufferOutputStream()
    with pa.ipc.new_stream(out, batch.schema) as writer:
        writer.write_table(batch)
    return out.getvalue().to_pybytes()


# --------------------------------------------------------------------------
# The sink
# --------------------------------------------------------------------------


class PerspectiveSink:
    """``contracts.DashboardSink`` backed by a real ``perspective.Server``.

    Three tables, matching contract 4 exactly:

    * ``positions`` -- indexed by ``symbol``, so pushing a row for a symbol
      that already exists *overwrites it in place* rather than appending.
      This is what lets a live position ticker show one row per symbol.
    * ``equity``    -- indexed by ``date``, same in-place-update behaviour
      for the equity curve (re-pushing today's point just corrects it).
    * ``fills``     -- no index: every ``update()`` call appends new rows,
      because a fill blotter is a log, not a snapshot.

    A single ``perspective.Server`` is created (unless one is supplied, which
    the test harness uses so the websocket handler and this sink share
    state), and a local, synchronous ``Client`` is bound to it via
    ``Server.new_local_client()`` -- this is the same call the module
    docstring for ``PerspectiveTornadoHandler`` uses to set up tables before
    handing the server to Tornado.  Only one sink per server (table names are
    server-global); a second one raises ``ValueError``.

    Updates are sent as typed Arrow batches, not lists of dicts: that is what
    makes this sink hold the same values a ``RecordingSink`` fed the same
    rows would (bit-exact floats, numpy scalars accepted, NaN -> null instead
    of the whole batch vanishing). See the module docstring, note 4.
    """

    def __init__(self, server: "perspective.Server | None" = None) -> None:
        self.server = server if server is not None else perspective.Server()
        self.client = self.server.new_local_client()
        clash = sorted(set(TABLE_NAMES) & set(self.client.get_hosted_table_names()))
        if clash:
            raise ValueError(
                f"this perspective.Server already hosts table(s) {clash}: only "
                "one PerspectiveSink per Server (table names are server-global)."
                " Reuse the existing sink, or pass a fresh perspective.Server()."
            )
        self.positions = self.client.table(
            dict(POSITIONS_SCHEMA), index="symbol", name="positions"
        )
        self.equity = self.client.table(
            dict(EQUITY_SCHEMA), index="date", name="equity"
        )
        self.fills = self.client.table(dict(FILLS_SCHEMA), name="fills")

    @staticmethod
    def _push(table, rows: Iterable[Mapping], schema, index: str | None) -> None:
        rows = [dict(r) for r in rows]
        if rows:
            table.update(_rows_to_arrow_ipc(rows, schema, index))

    def update_positions(self, rows: Iterable[dict]) -> None:
        self._push(self.positions, rows, POSITIONS_SCHEMA, "symbol")

    def update_equity(self, rows: Iterable[dict]) -> None:
        self._push(self.equity, rows, EQUITY_SCHEMA, "date")

    def update_fills(self, rows: Iterable[dict]) -> None:
        self._push(self.fills, rows, FILLS_SCHEMA, None)

    def table_sizes(self) -> dict[str, int]:
        """Rows actually held by each table (what a viewer will see)."""
        return {
            "positions": self.positions.size(),
            "equity": self.equity.size(),
            "fills": self.fills.size(),
        }


# --------------------------------------------------------------------------
# Tornado wiring
# --------------------------------------------------------------------------


def make_app(
    server: "perspective.Server",
    websocket_max_message_size: int = DEFAULT_WEBSOCKET_MAX_MESSAGE_SIZE,
) -> tornado.web.Application:
    """Build the Tornado app: one websocket route, one static page.

    ``check_origin`` on the handler defaults to accepting everything (see
    ``PerspectiveTornadoHandler.check_origin`` in the installed package --
    it always returns ``True``); combined with the total lack of auth, this
    is exactly why :func:`serve` refuses to bind off-loopback without
    ``--host`` being explicit. See the module docstring's security warning.
    """
    return tornado.web.Application(
        [
            (r"/ws", PerspectiveTornadoHandler, {"perspective_server": server}),
            (
                r"/(.*)",
                tornado.web.StaticFileHandler,
                {"path": str(STATIC_DIR), "default_filename": "index.html"},
            ),
        ],
        websocket_max_message_size=websocket_max_message_size,
    )


def serve(sink: PerspectiveSink, port: int, host: str = "127.0.0.1") -> None:
    """Serve ``sink``'s tables forever. Blocks; run this as your process's
    main loop (the CLI below is a thin wrapper around it).

    SECURITY: binds to ``host`` verbatim with no auth in front of it -- see
    the module docstring. Only pass ``host="0.0.0.0"`` (or another
    non-loopback address) when you mean to expose this to your network.
    """
    app = make_app(sink.server)
    app.listen(port, address=host)
    print(f"[dashboard] serving on http://{host}:{port}/  (websocket: /ws)")
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(
            f"[dashboard] WARNING: bound to {host} -- PerspectiveTornadoHandler "
            "has NO authentication. Anyone who can reach this host:port can "
            "read and write every table.",
            file=sys.stderr,
        )
    tornado.ioloop.IOLoop.current().start()


def _port_unavailable(host: str, port: int) -> str | None:
    """Return the bind error for ``host:port``, or None if it is free.

    Uses the same ``bind_sockets`` (SO_REUSEADDR) Tornado's ``listen`` uses,
    so "free" here means ``serve`` will be able to bind it too (barring a
    race with another process in between)."""
    try:
        socks = tornado.netutil.bind_sockets(port, address=host)
    except OSError as exc:
        return str(exc)
    for s in socks:
        s.close()
    return None


# --------------------------------------------------------------------------
# Demo / replay data
# --------------------------------------------------------------------------


def _demo_dataset() -> tuple[list[dict], list[dict], list[dict]]:
    """A tiny, self-contained dataset so the page shows *something* useful
    when the execution module (running concurrently in another agent) hasn't
    written its CSVs yet."""
    symbols = {"AAPL": 189.0, "MSFT": 412.0, "GOOG": 168.0}
    qty = {"AAPL": 120.0, "MSFT": 45.0, "GOOG": -30.0}
    positions_rows = [
        {"symbol": s, "qty": qty[s], "last": px, "value": qty[s] * px}
        for s, px in symbols.items()
    ]
    dates = pd.bdate_range("2026-08-01", periods=15)
    equity = 1_000_000.0
    equity_rows = []
    rng_steps = [
        1250, -800, 2100, 600, -1500, 3000, -400, 1800, 900, -2200,
        1600, 500, -700, 2400, 1100,
    ]
    for d, step in zip(dates, rng_steps):
        equity += step
        equity_rows.append({"date": d.date().isoformat(), "equity": equity})
    fills_rows = [
        {"ts": f"{dates[0].date().isoformat()}T14:30:00", "symbol": "AAPL", "side": "BUY", "qty": 120.0, "price": 187.5},
        {"ts": f"{dates[1].date().isoformat()}T14:31:00", "symbol": "MSFT", "side": "BUY", "qty": 45.0, "price": 409.0},
        {"ts": f"{dates[2].date().isoformat()}T14:32:00", "symbol": "GOOG", "side": "SELL", "qty": 30.0, "price": 170.0},
    ]
    return positions_rows, equity_rows, fills_rows


def _load_positions_csv(path: Path) -> list[dict]:
    """Reuse ``contracts.read_positions_csv`` -- it's the one place the
    stack knows how the execution module writes this file."""
    snapshot = read_positions_csv(path)
    return snapshot.to_rows()


def _load_equity_csv(path: Path) -> tuple[list[dict], str]:
    """Load an equity curve CSV into EQUITY_SCHEMA rows.

    Contract gap hit in practice: ``contracts.py`` defines
    ``POSITIONS_CSV_COLUMNS``/``write_positions_csv``/``read_positions_csv``
    for the positions file, but has no equivalent for the equity curve, so
    there's no agreed single column name. The execution module (built
    concurrently, in another agent's module) in fact writes one column per
    allocator variant -- ``equity_hrp``, ``equity_equal_engine``,
    ``equity_equal_pandas`` -- not a plain ``equity`` column. Rather than
    silently fudging a number or hard-failing, we take a plain ``equity``
    column if present, else the *first* ``equity_*`` column (columns are
    written in a stable order by the execution module, so "first" is
    deterministic), and say on stdout and in the summary JSON exactly which
    column was used. See this module's final report for the suggested
    contracts.py addition (an ``EQUITY_CSV_COLUMNS`` + read/write pair,
    mirroring the positions one) that would remove this ambiguity.

    A blank equity cell becomes NaN here and null in the table (it is *not*
    dropped); the CLI summary records the table sizes actually served.
    """
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    date_col = cols.get("date") or cols.get("as_of")
    equity_col = cols.get("equity")
    if equity_col is None:
        candidates = [c for c in df.columns if c.lower().startswith("equity")]
        if candidates:
            equity_col = candidates[0]
    if date_col is None or equity_col is None:
        raise ValueError(
            f"{path} does not look like an equity curve "
            f"(need a 'date' column and an 'equity' or 'equity_*' column, "
            f"got {list(df.columns)})"
        )
    rows = []
    for d, e in zip(df[date_col], df[equity_col]):
        rows.append({"date": str(d)[:10], "equity": float(e)})
    return rows, equity_col


def _load_fills_csv(path: Path) -> list[dict]:
    df = pd.read_csv(path)
    return df.to_dict(orient="records")


@dataclass
class ReplayData:
    """What the CLI loads before serving (real replay or synthetic demo)."""

    positions_rows: list[dict]
    equity_rows: list[dict]
    fills_rows: list[dict]
    is_demo: bool
    equity_col: str | None
    fills_csv: Path | None  # the fills file actually loaded, None if none
    fallback_reason: str | None  # why we fell back to the demo, if we did


def load_replay(
    equity_csv: Path, positions_csv: Path, fills_csv: Path | None
) -> ReplayData:
    """Try to replay real execution-module output; fall back to a synthetic
    demo if it isn't there yet (the execution module is built concurrently
    by a different agent, so at CLI-run time it may simply not exist).

    ``fills_csv`` is loaded only if given *and* present; it is never
    silently swapped for another run's file (a custom ``--replay`` used to
    pick up the repo's default fills, mixing sources on one screen).
    """
    equity_csv, positions_csv = Path(equity_csv), Path(positions_csv)
    missing = [str(p) for p in (equity_csv, positions_csv) if not p.exists()]
    if missing:
        reason = "not found: " + ", ".join(missing)
    else:
        try:
            positions_rows = _load_positions_csv(positions_csv)
            equity_rows, equity_col = _load_equity_csv(equity_csv)
            fills_path = (
                Path(fills_csv)
                if fills_csv is not None and Path(fills_csv).exists()
                else None
            )
            fills_rows = _load_fills_csv(fills_path) if fills_path else []
            return ReplayData(
                positions_rows, equity_rows, fills_rows, False, equity_col,
                fills_path, None,
            )
        except Exception as exc:  # noqa: BLE001 -- deliberately broad: any
            # parse failure here should degrade to the demo, not crash the
            # dashboard, since the writer (another agent's module) may still
            # be mid-write or using a slightly different column layout.
            reason = f"could not parse ({exc!r})"
    positions_rows, equity_rows, fills_rows = _demo_dataset()
    return ReplayData(positions_rows, equity_rows, fills_rows, True, None, None, reason)


def load_or_demo(
    equity_csv: Path, positions_csv: Path, fills_csv: Path | None
) -> tuple[list[dict], list[dict], list[dict], bool, str | None]:
    """Tuple-returning form of :func:`load_replay`, kept for callers of the
    original API.

    Returns ``(positions_rows, equity_rows, fills_rows, is_demo, equity_col)``,
    where ``equity_col`` is the source column name used for the equity curve
    when replaying real data (``None`` in demo mode) -- see
    :func:`_load_equity_csv` for why that isn't always just ``"equity"``.
    """
    data = load_replay(equity_csv, positions_csv, fills_csv)
    if data.is_demo:
        print(
            f"[dashboard] {data.fallback_reason}; falling back to synthetic demo data",
            file=sys.stderr,
        )
    return (
        data.positions_rows, data.equity_rows, data.fills_rows,
        data.is_demo, data.equity_col,
    )


# --------------------------------------------------------------------------
# In-process websocket smoke test (the wire this module exists to prove)
# --------------------------------------------------------------------------

# Deliberately not a "round" number: the list-of-dicts JSON path used to
# return this 1 ulp off (...51); the Arrow path must return it bit-exact.
_SELFTEST_FLOAT = 98.27639451941653


def run_wire_selftest(host: str = "127.0.0.1", timeout: float = 10.0) -> dict:
    """Start a *real* Tornado+Perspective server on an OS-assigned free port
    in a background thread (its own asyncio loop), push rows through
    :class:`PerspectiveSink`, then connect an actual websocket client
    (``tornado.websocket.websocket_connect`` + ``perspective.AsyncClient``)
    from this thread's asyncio loop and read them back over the wire.

    This is the same mechanism ``tests/test_dashboard.py`` exercises; it's
    factored out here so the CLI can run it once at startup (proof the wire
    is live before serving) and record its result in
    ``results/dashboard_summary.json``. Returns a dict of the numbers that
    go in that file.
    """
    server = perspective.Server()
    sink = PerspectiveSink(server=server)

    # Push once, then push an update to the *same* symbol -- this is what
    # proves the indexed table overwrites in place rather than appending.
    sink.update_positions([{"symbol": "AAPL", "qty": 10.0, "last": 100.0, "value": 1000.0}])
    sink.update_positions([{"symbol": "AAPL", "qty": 25.0, "last": 101.5, "value": 2537.5}])
    sink.update_positions([{"symbol": "MSFT", "qty": 5.0, "last": _SELFTEST_FLOAT, "value": 5.0 * _SELFTEST_FLOAT}])
    sink.update_equity([{"date": "2026-09-24", "equity": 1_000_000.0}])
    sink.update_equity([{"date": "2026-09-25", "equity": 1_004_000.0}])
    sink.update_fills([{"ts": "2026-09-25T14:30:00", "symbol": "AAPL", "side": "BUY", "qty": 25.0, "price": 101.5}])

    app = make_app(server)
    sockets = tornado.netutil.bind_sockets(0, address=host)
    port = sockets[0].getsockname()[1]

    ready = threading.Event()
    loop_holder: dict = {}

    def server_main() -> None:
        asyncio.set_event_loop(asyncio.new_event_loop())
        io_loop = tornado.ioloop.IOLoop.current()
        loop_holder["io_loop"] = io_loop
        http_server = tornado.httpserver.HTTPServer(app)
        http_server.add_sockets(sockets)
        loop_holder["http_server"] = http_server
        io_loop.add_callback(ready.set)
        io_loop.start()

    thread = threading.Thread(target=server_main, daemon=True)
    thread.start()
    if not ready.wait(timeout=timeout):
        raise RuntimeError("dashboard self-test server did not start in time")

    async def client_check() -> dict:
        import tornado.websocket

        # Responses are fed to the AsyncClient on *this* (the client's) event
        # loop, as perspective's reference test does -- not on the server
        # thread's IOLoop. Keep strong refs so tasks aren't GC'd mid-flight.
        loop = asyncio.get_running_loop()
        client_holder: dict = {}
        pending: set = set()

        def on_message(msg):
            if msg is None:  # connection closed
                return
            task = loop.create_task(client_holder["client"].handle_response(msg))
            pending.add(task)
            task.add_done_callback(pending.discard)

        conn = await tornado.websocket.websocket_connect(
            f"ws://{host}:{port}/ws", on_message_callback=on_message
        )

        async def handle_request(msg: bytes) -> None:
            conn.write_message(msg, binary=True)

        client = perspective.AsyncClient(handle_request)
        client_holder["client"] = client

        try:
            out = {"hosted_tables": sorted(await client.get_hosted_table_names())}
            for name in TABLE_NAMES:
                table = await client.open_table(name)
                view = await table.view()
                out[name] = await view.to_records()
            return out
        finally:
            conn.close()

    try:
        result = asyncio.run(asyncio.wait_for(client_check(), timeout=timeout))
    finally:
        io_loop = loop_holder["io_loop"]
        http_server = loop_holder["http_server"]
        io_loop.add_callback(http_server.stop)
        io_loop.add_callback(io_loop.stop)
        thread.join(timeout=timeout)

    positions = result["positions"]
    aapl_rows = [r for r in positions if r["symbol"] == "AAPL"]
    msft_rows = [r for r in positions if r["symbol"] == "MSFT"]
    return {
        "port": port,
        "hosted_tables": result["hosted_tables"],
        "positions_rows_read_back": positions,
        "equity_rows_read_back": result["equity"],
        "fills_rows_read_back": result["fills"],
        "indexed_overwrite_ok": (
            len(positions) == 2 and len(aapl_rows) == 1 and aapl_rows[0]["qty"] == 25.0
        ),
        "float_bit_exact_ok": (
            len(msft_rows) == 1 and msft_rows[0]["last"] == _SELFTEST_FLOAT
        ),
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _previous_wire_selftest(path: Path) -> dict | None:
    try:
        block = json.loads(path.read_text()).get("wire_selftest")
    except (OSError, ValueError, AttributeError):
        return None
    if isinstance(block, dict) and block.get("port_used") is not None:
        return block
    return None


def _write_summary(selftest: dict | None, replay_info: dict) -> Path:
    """Write ``results/dashboard_summary.json``.

    ``selftest=None`` means ``--no-selftest``: the websocket evidence from
    the last run that *did* measure it is carried over (flagged
    ``measured_this_run: false``) instead of being overwritten with nulls.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "dashboard_summary.json"
    if selftest is None:
        previous = _previous_wire_selftest(out_path)
        if previous is not None:
            wire = dict(previous)
            wire["measured_this_run"] = False
            wire["note"] = (
                "carried over unchanged from an earlier run; this run used "
                "--no-selftest"
            )
        else:
            wire = {
                "port_used": None,
                "measured_this_run": False,
                "note": "--no-selftest and no earlier self-test result on disk",
            }
    else:
        wire = {
            "port_used": selftest["port"],
            "measured_this_run": True,
            "hosted_tables": selftest["hosted_tables"],
            "positions_rows_read_back_over_websocket": selftest["positions_rows_read_back"],
            "equity_rows_read_back_over_websocket": selftest["equity_rows_read_back"],
            "fills_rows_read_back_over_websocket": selftest["fills_rows_read_back"],
            "indexed_update_overwrote_in_place": selftest["indexed_overwrite_ok"],
            "float_round_trip_bit_exact": selftest.get("float_bit_exact_ok"),
        }
    summary = {
        "perspective_version": perspective.__version__,
        "tables": {
            "positions": {"schema": POSITIONS_SCHEMA, "index": "symbol"},
            "equity": {"schema": EQUITY_SCHEMA, "index": "date"},
            "fills": {"schema": FILLS_SCHEMA, "index": None},
        },
        "update_path": "Arrow IPC bytes (typed from contracts schemas), not list-of-dicts JSON",
        "npm_packages_used_by_static_index_html": {
            "@perspective-dev/client": perspective.__version__,
            "@perspective-dev/viewer": perspective.__version__,
            "@perspective-dev/viewer-datagrid": perspective.__version__,
            "@perspective-dev/viewer-charts": perspective.__version__,
            "note": (
                "renamed from @finos/perspective* upstream; see module "
                "docstring in quantstack/dashboard/server.py"
            ),
        },
        "wire_selftest": wire,
        "replay": replay_info,
    }
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    return out_path


def _size_warnings(loaded: dict[str, int], served: dict[str, int]) -> list[str]:
    return [
        f"{name}: {loaded[name]} row(s) loaded but table holds {served[name]} "
        "(duplicate index keys collapse by design; any other gap is lost data)"
        for name in TABLE_NAMES
        if loaded[name] != served[name]
    ]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m quantstack.dashboard.server",
        description=(
            "Serve the quantstack dashboard (Perspective + Tornado). "
            "SECURITY: the websocket handler has NO authentication -- binds "
            "to 127.0.0.1 by default; pass --host 0.0.0.0 to expose it on "
            "your network (only do this on a trusted network)."
        ),
    )
    parser.add_argument("--port", type=int, default=8080, help="port to serve on (default: 8080)")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help=(
            "address to bind to (default: 127.0.0.1, loopback-only). "
            "Pass 0.0.0.0 to expose this on your network -- the websocket "
            "handler has no authentication, so only do this on a trusted "
            "network."
        ),
    )
    parser.add_argument(
        "--replay",
        nargs=2,
        metavar=("EQUITY_CSV", "POSITIONS_CSV"),
        default=[str(DEFAULT_EQUITY_CSV), str(DEFAULT_POSITIONS_CSV)],
        help=(
            "CSV files written by the execution module to load into the "
            "equity/positions tables at startup "
            f"(default: {DEFAULT_EQUITY_CSV} {DEFAULT_POSITIONS_CSV}). "
            "If either file is missing, a small synthetic demo dataset is "
            "served instead so the page still shows something."
        ),
    )
    parser.add_argument(
        "--fills",
        metavar="FILLS_CSV",
        default=None,
        help=(
            f"fills CSV for the fills table (default: {FILLS_CSV_NAME} in the "
            "same directory as EQUITY_CSV, if it exists; otherwise no fills "
            "are loaded -- never another run's file)"
        ),
    )
    parser.add_argument(
        "--no-selftest",
        action="store_true",
        help=(
            "skip the startup websocket self-test (it's fast; mainly for CI). "
            "The previous self-test result in the summary JSON is kept."
        ),
    )
    args = parser.parse_args(argv)

    # Fail fast, before the self-test and before touching the summary JSON.
    bind_error = _port_unavailable(args.host, args.port)
    if bind_error is not None:
        print(
            f"[dashboard] cannot bind {args.host}:{args.port}: {bind_error} "
            "-- pick another --port",
            file=sys.stderr,
        )
        raise SystemExit(2)

    equity_csv, positions_csv = Path(args.replay[0]), Path(args.replay[1])
    if args.fills is not None:
        fills_csv = Path(args.fills)
        if not fills_csv.exists():
            print(f"[dashboard] --fills {fills_csv} not found; no fills will be loaded")
    else:
        fills_csv = equity_csv.parent / FILLS_CSV_NAME

    data = load_replay(equity_csv, positions_csv, fills_csv)
    if data.is_demo:
        print(
            f"[dashboard] replay unavailable ({data.fallback_reason}) -- the "
            "execution module may still be building; serving synthetic demo "
            "data instead"
        )
    else:
        print(
            f"[dashboard] replaying {positions_csv} and {equity_csv} "
            f"(equity column: {data.equity_col!r}; fills: "
            f"{data.fills_csv if data.fills_csv else 'none'})"
        )

    server = perspective.Server()
    sink = PerspectiveSink(server=server)
    sink.update_positions(data.positions_rows)
    sink.update_equity(data.equity_rows)
    sink.update_fills(data.fills_rows)
    loaded = {
        "positions": len(data.positions_rows),
        "equity": len(data.equity_rows),
        "fills": len(data.fills_rows),
    }
    served = sink.table_sizes()
    warnings = _size_warnings(loaded, served)
    for w in warnings:
        print(f"[dashboard] WARNING: {w}", file=sys.stderr)

    if args.no_selftest:
        selftest = None
        print("[dashboard] --no-selftest: keeping the previous self-test result")
    else:
        print("[dashboard] running in-process websocket self-test...")
        selftest = run_wire_selftest()
        print(
            f"[dashboard] self-test OK on port {selftest['port']}: "
            f"{len(selftest['positions_rows_read_back'])} position row(s), "
            f"indexed overwrite ok={selftest['indexed_overwrite_ok']}, "
            f"float bit-exact ok={selftest['float_bit_exact_ok']}"
        )

    summary_path = _write_summary(
        selftest,
        replay_info={
            "is_demo": data.is_demo,
            "fallback_reason": data.fallback_reason,
            "equity_csv": str(equity_csv),
            "positions_csv": str(positions_csv),
            "fills_csv": str(data.fills_csv) if data.fills_csv else None,
            "equity_source_column": data.equity_col,
            # rows read from the CSVs (or the demo) ...
            "n_positions": loaded["positions"],
            "n_equity_points": loaded["equity"],
            "n_fills": loaded["fills"],
            # ... and rows the served tables actually hold
            "table_sizes_after_load": served,
            "table_size_warnings": warnings,
        },
    )
    print(f"[dashboard] wrote {summary_path}")

    try:
        serve(sink, port=args.port, host=args.host)
    except KeyboardInterrupt:
        print("\n[dashboard] stopped")


if __name__ == "__main__":
    main()
