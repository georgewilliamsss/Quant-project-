"""Tests for quantstack.dashboard.server.

The whole point of this module (per the article) is that the display wire is
*real*: a Perspective ``Table`` living in one Python object gets read back
through an actual websocket, not a mock. So the main tests do exactly that
end to end:

  1. start the real Tornado app on an OS-assigned free port with
     :class:`BackgroundDashboard` -- a background thread running its own
     asyncio/Tornado event loop (its lifecycle is tested on its own below);
  2. push rows into a :class:`PerspectiveSink` from the main thread
     (including a second update to the same symbol, to prove the indexed
     table overwrites in place rather than appending);
  3. from the main thread, open a *second*, independent asyncio loop
     (``asyncio.run``) and connect an actual websocket client --
     ``tornado.websocket.websocket_connect`` paired with
     ``perspective.AsyncClient`` -- across a real loopback TCP socket to
     ``/ws``, then read the tables back with ``open_table(...).view()``.
     The client helper here is written independently of the module's own
     self-test client, so the two cannot share a bug.

No mocking of the wire was needed: ``websocket-client`` (the package used by
perspective's own ``tests/async/test_websocket_client.py``) isn't installed
here, but Tornado already ships an async websocket client, which is a fully
real alternative (see the module docstring's version-skew notes).

The CLI tests run ``main()`` with every results path redirected into
``tmp_path`` so they never read or write the real ``results/`` directory.
The one browser test is ``@pytest.mark.slow`` and skips without Chromium.
Everything else runs in a few seconds.
"""

from __future__ import annotations

import asyncio
import datetime
import html.parser
import importlib.util
import json
import math
import os
import random
import re
import socket
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import perspective
import pytest
import tornado.httpclient
import tornado.netutil
import tornado.websocket

import quantstack.dashboard.server as server_mod
from quantstack.contracts import (
    EQUITY_SCHEMA,
    FILLS_SCHEMA,
    POSITIONS_SCHEMA,
    RecordingSink,
)
from quantstack.dashboard.server import (
    BackgroundDashboard,
    PerspectiveSink,
    make_app,
    npm_pins_in_index_html,
    origin_allowed,
    run_wire_selftest,
    serve_in_background,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# PerspectiveSink in isolation (no network) -- schema + in-place update
# --------------------------------------------------------------------------


def test_sink_creates_tables_matching_contracts_schema():
    sink = PerspectiveSink()
    assert sink.positions.schema() == dict(POSITIONS_SCHEMA)
    assert sink.equity.schema() == dict(EQUITY_SCHEMA)
    assert sink.fills.schema() == dict(FILLS_SCHEMA)
    assert sink.meta.schema() == dict(server_mod.META_SCHEMA)
    assert sink.positions.get_index() == "symbol"
    assert sink.equity.get_index() == "date"
    assert sink.fills.get_index() is None
    assert sink.meta.get_index() == "key"
    assert sink.get_meta() == {}  # unlabeled until someone calls set_meta


def test_sink_positions_update_overwrites_by_symbol_index():
    """Same contract behaviour as RecordingSink.update_positions, but backed
    by a real Perspective indexed Table instead of a plain dict."""
    sink = PerspectiveSink()
    sink.update_positions([{"symbol": "AAPL", "qty": 10.0, "last": 100.0, "value": 1000.0}])
    sink.update_positions([{"symbol": "AAPL", "qty": 30.0, "last": 105.0, "value": 3150.0}])
    sink.update_positions([{"symbol": "MSFT", "qty": 5.0, "last": 400.0, "value": 2000.0}])

    rows = {r["symbol"]: r for r in sink.positions.view().to_records()}
    assert set(rows) == {"AAPL", "MSFT"}
    assert rows["AAPL"]["qty"] == 30.0  # latest write wins, still one row
    assert sink.positions.size() == 2


def test_sink_equity_update_overwrites_by_date_index():
    sink = PerspectiveSink()
    sink.update_equity([{"date": "2026-09-24", "equity": 1_000_000.0}])
    sink.update_equity([{"date": "2026-09-24", "equity": 1_010_000.0}])  # correction
    sink.update_equity([{"date": "2026-09-25", "equity": 1_015_000.0}])

    rows = {r["date"]: r["equity"] for r in sink.equity.view().to_records()}
    assert rows == {"2026-09-24": 1_010_000.0, "2026-09-25": 1_015_000.0}
    assert sink.equity.size() == 2


def test_sink_fills_are_append_only():
    sink = PerspectiveSink()
    fill = {"ts": "2026-09-25T14:30:00", "symbol": "AAPL", "side": "BUY", "qty": 10.0, "price": 100.0}
    sink.update_fills([fill])
    sink.update_fills([fill])  # identical row again -- no index, so it appends
    assert sink.fills.size() == 2


def _random_stream(seed: int = 7, steps: int = 200):
    """A random, deliberately *non-round* sequence of sink updates (random
    batch sizes, repeated symbols/dates, full-precision floats). Round
    numbers like 10.0 / 1_000_000.0 are exactly representable and would hide
    the ~1 ulp drift of perspective's list-of-dicts JSON path."""
    rng = random.Random(seed)
    symbols = ["AAPL", "MSFT", "GOOG", "AMZN", "JPM", "XOM"]
    for i in range(steps):
        positions = [
            {
                "symbol": rng.choice(symbols),
                "qty": rng.uniform(-5_000, 5_000),
                "last": rng.uniform(1, 800),
                "value": rng.uniform(-2e6, 2e6),
            }
            for _ in range(rng.randint(1, 4))
        ]
        # dates repeat (i // 2) so indexed corrections are exercised too
        equity = [{
            "date": (datetime.date(2026, 1, 1) + datetime.timedelta(days=i // 2)).isoformat(),
            "equity": 1e6 * math.exp(rng.gauss(0, 0.2)),
        }]
        fills = [
            {
                "ts": f"2026-01-01T{i // 60:02d}:{i % 60:02d}:00",
                "symbol": rng.choice(symbols),
                "side": rng.choice(["BUY", "SELL"]),
                "qty": rng.uniform(0, 1_000),
                "price": rng.uniform(1, 800),
            }
            for _ in range(rng.randint(0, 2))
        ]
        yield positions, equity, fills


def test_sink_round_trips_exactly_like_recording_sink():
    """Feed the *same* random, non-round stream to contracts.RecordingSink
    and to PerspectiveSink and require bit-for-bit equal state: positions
    (last row per symbol), equity (last value per date) and fills (every row,
    in order). This held only after switching the update path from
    list-of-dicts (JSON, ~1 ulp drift) to typed Arrow batches."""
    recorder, sink = RecordingSink(), PerspectiveSink()
    for positions, equity, fills in _random_stream():
        for target in (recorder, sink):
            target.update_positions(positions)
            target.update_equity(equity)
            target.update_fills(fills)

    positions_out = {r["symbol"]: r for r in sink.positions.view().to_records()}
    equity_out = {r["date"]: r["equity"] for r in sink.equity.view().to_records()}
    fills_out = sink.fills.view().to_records()

    assert positions_out == recorder.positions  # exact float equality
    assert equity_out == recorder.equity
    assert fills_out == recorder.fills
    assert sink.positions.size() == len(recorder.positions)
    assert sink.equity.size() == len(recorder.equity)


def test_partial_rows_replace_the_whole_row_like_recording_sink():
    """Documented semantics: every schema column is sent for every row, so a
    key missing from a row nulls that cell (the row *replaces* the stored
    one, as ``RecordingSink.positions[symbol] = dict(r)`` does) -- and the
    outcome no longer depends on what else is in the batch (it used to keep
    the old cells only when *no* row in the batch had that column)."""
    full = {"symbol": "AAPL", "qty": 10.0, "last": 100.0, "value": 1000.0}
    partial = {"symbol": "AAPL", "qty": 20.0}
    other = {"symbol": "MSFT", "qty": 1.0, "last": 2.0, "value": 2.0}

    alone, mixed, recorder = PerspectiveSink(), PerspectiveSink(), RecordingSink()
    for target in (alone, recorder):
        target.update_positions([full])
        target.update_positions([partial])
    mixed.update_positions([full])
    mixed.update_positions([partial, other])

    expected = {"symbol": "AAPL", "qty": 20.0, "last": None, "value": None}
    alone_rows = {r["symbol"]: r for r in alone.positions.view().to_records()}
    mixed_rows = {r["symbol"]: r for r in mixed.positions.view().to_records()}
    assert alone_rows["AAPL"] == expected
    assert mixed_rows["AAPL"] == expected
    assert {k: recorder.positions["AAPL"].get(k) for k in POSITIONS_SCHEMA} == expected

    # keys outside the schema are ignored, not an error
    alone.update_positions([{**full, "sector": "tech"}])
    assert alone.positions.view().to_records() == [full]


def test_equity_date_keys_are_normalised_so_a_day_appears_once():
    sink = PerspectiveSink()
    for i, day in enumerate([
        pd.Timestamp("2026-01-05"),                  # isoformat() has T00:00:00
        datetime.date(2026, 1, 5),
        datetime.datetime(2026, 1, 5, 16, 0),        # intraday -> same day
        np.datetime64("2026-01-05T00:00:00"),
        "2026-01-05T00:00:00",
        "2026-01-05 00:00:00",
        "2026-01-05",
    ]):
        sink.update_equity([{"date": day, "equity": float(i)}])
    assert sink.equity.size() == 1
    assert sink.equity.view().to_records() == [{"date": "2026-01-05", "equity": 6.0}]
    sink.update_equity([{"date": "not-a-date", "equity": 1.0}])  # other strings verbatim
    assert {r["date"] for r in sink.equity.view().to_records()} == {"2026-01-05", "not-a-date"}


def test_bad_value_raises_valueerror_naming_the_column_and_sends_nothing():
    sink = PerspectiveSink()
    with pytest.raises(ValueError, match=r"row 1: column 'qty'"):
        sink.update_fills([
            {"ts": "t0", "symbol": "AAPL", "side": "BUY", "qty": 1.0, "price": 1.0},
            {"ts": "t1", "symbol": "AAPL", "side": "BUY", "qty": "ten", "price": 1.0},
        ])
    assert sink.fills.size() == 0


def test_sink_nan_or_inf_does_not_drop_the_batch():
    """perspective 5.5.1 silently drops a whole list-of-dicts update if any
    value is NaN/inf (no exception). The execution strategy's snapshot uses
    NaN for unpriced symbols, so a whole day's positions would vanish. The
    Arrow path must keep every row, with NaN as null."""
    sink = PerspectiveSink()
    sink.update_equity([
        {"date": "2026-01-01", "equity": 1.0},
        {"date": "2026-01-02", "equity": float("nan")},
        {"date": "2026-01-03", "equity": 3.0},
    ])
    assert sink.equity.view().to_records() == [
        {"date": "2026-01-01", "equity": 1.0},
        {"date": "2026-01-02", "equity": None},
        {"date": "2026-01-03", "equity": 3.0},
    ]
    sink.update_positions([
        {"symbol": "AAPL", "qty": 10.0, "last": float("nan"), "value": float("nan")},
        {"symbol": "MSFT", "qty": math.inf, "last": 400.0, "value": math.inf},
        {"symbol": "GOOG", "qty": 3.0, "last": 150.0, "value": 450.0},
    ])
    assert sink.positions.size() == 3
    rows = {r["symbol"]: r for r in sink.positions.view().to_records()}
    assert rows["AAPL"]["last"] is None and rows["AAPL"]["qty"] == 10.0
    assert rows["GOOG"]["value"] == 450.0


def test_sink_accepts_numpy_scalars_and_dates_like_recording_sink():
    """RecordingSink accepts numpy scalars and datetime.date; the JSON path
    raised 'not JSON serializable'. Floats are coerced with float(v) -- the
    same coercion RecordingSink.update_equity applies."""
    sink = PerspectiveSink()
    sink.update_positions([
        {"symbol": "AAPL", "qty": np.int64(7), "last": np.float32(0.1), "value": np.float64(0.7)}
    ])
    sink.update_equity([{"date": datetime.date(2026, 1, 5), "equity": np.int64(1_000_001)}])
    sink.update_fills([{"ts": datetime.datetime(2026, 1, 5, 14, 30), "symbol": "AAPL",
                        "side": "BUY", "qty": np.int32(7), "price": np.float64(0.1)}])
    assert sink.positions.view().to_records() == [
        {"symbol": "AAPL", "qty": 7.0, "last": float(np.float32(0.1)), "value": 0.7}
    ]
    assert sink.equity.view().to_records() == [{"date": "2026-01-05", "equity": 1_000_001.0}]
    assert sink.fills.view().to_records()[0]["ts"] == "2026-01-05T14:30:00"


def test_sink_requires_index_key_like_recording_sink():
    sink = PerspectiveSink()
    with pytest.raises(KeyError):
        sink.update_positions([{"qty": 1.0, "last": 1.0, "value": 1.0}])
    with pytest.raises(KeyError):
        RecordingSink().update_positions([{"qty": 1.0, "last": 1.0, "value": 1.0}])


def test_one_sink_per_server_is_enforced_with_a_clear_error():
    server = perspective.Server()
    PerspectiveSink(server=server)
    with pytest.raises(ValueError, match="one PerspectiveSink per Server"):
        PerspectiveSink(server=server)


# --------------------------------------------------------------------------
# The real websocket wire: server in a background thread + a real client
# --------------------------------------------------------------------------


async def _read_tables_over_websocket(ws_url: str, table_names: list[str], headers=None) -> dict:
    """Connect a real websocket client to the running server and read each
    named table back with view().to_records(). Mirrors the pattern in the
    installed perspective package's own
    perspective/tests/async/test_websocket_client.py and
    perspective/tests/async/test_async_client.py: an AsyncClient whose
    `handle_request` callback writes bytes to the socket, fed incoming bytes
    via `handle_response` from the websocket's on_message callback."""
    client_holder: dict = {}
    loop = asyncio.get_running_loop()
    tasks: set = set()

    def on_message(msg):
        if msg is None:  # connection closed
            return
        task = loop.create_task(client_holder["client"].handle_response(msg))
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    request = tornado.httpclient.HTTPRequest(ws_url, headers=headers or {})
    conn = await tornado.websocket.websocket_connect(request, on_message_callback=on_message)

    async def handle_request(msg: bytes) -> None:
        conn.write_message(msg, binary=True)

    client = perspective.AsyncClient(handle_request)
    client_holder["client"] = client

    try:
        hosted = await client.get_hosted_table_names()
        out = {"hosted_tables": sorted(hosted)}
        for name in table_names:
            table = await client.open_table(name)
            view = await table.view()
            out[name] = await view.to_records()
        return out
    finally:
        conn.close()


def _read(ws_url, names, headers=None) -> dict:
    return asyncio.run(asyncio.wait_for(_read_tables_over_websocket(ws_url, names, headers), 10.0))


async def _handshake(ws_url: str, headers: dict) -> int:
    """101 if the upgrade is accepted, else the HTTP status code."""
    try:
        conn = await tornado.websocket.websocket_connect(
            tornado.httpclient.HTTPRequest(ws_url, headers=headers)
        )
    except tornado.httpclient.HTTPClientError as exc:
        return exc.code
    conn.close()
    return 101


def _status(ws_url: str, headers: dict) -> int:
    return asyncio.run(asyncio.wait_for(_handshake(ws_url, headers), 10.0))


def test_websocket_wire_reads_back_pushed_rows_with_indexed_overwrite():
    server = perspective.Server()
    sink = PerspectiveSink(server=server)
    with BackgroundDashboard(server).start() as dash:  # a bare Server works too
        # Two writes to the same symbol: the *second* value must be the one
        # that comes back over the wire, and there must still be one row.
        # Pushed while the server thread is already serving.
        sink.update_positions([{"symbol": "AAPL", "qty": 10.0, "last": 100.0, "value": 1000.0}])
        sink.update_positions([{"symbol": "AAPL", "qty": 40.0, "last": 102.0, "value": 4080.0}])
        sink.update_positions([{"symbol": "MSFT", "qty": 5.0, "last": 400.0, "value": 2000.0}])
        sink.update_equity([{"date": "2026-09-24", "equity": 1_000_000.0}])
        sink.update_equity([{"date": "2026-09-25", "equity": 1_006_000.0}])
        result = _read(dash.ws_url, ["positions", "equity"])

    assert set(result["hosted_tables"]) == {"positions", "equity", "fills", "meta"}

    # Check the row count on the raw wire result *before* collapsing it into
    # a dict keyed by symbol -- a dict would silently hide an appended
    # duplicate AAPL row (an unindexed table would otherwise still pass).
    assert len(result["positions"]) == 2
    assert sum(r["symbol"] == "AAPL" for r in result["positions"]) == 1
    assert len(result["equity"]) == 2

    positions = {r["symbol"]: r for r in result["positions"]}
    assert set(positions) == {"AAPL", "MSFT"}
    assert positions["AAPL"]["qty"] == 40.0  # overwrote in place, not appended
    assert positions["AAPL"]["value"] == 4080.0

    equity = {r["date"]: r["equity"] for r in result["equity"]}
    assert equity == {"2026-09-24": 1_000_000.0, "2026-09-25": 1_006_000.0}


def test_run_wire_selftest_helper_matches_direct_wire_test():
    """The same helper the CLI uses to populate dashboard_summary.json --
    exercised here too, so a regression in it fails the test suite, not just
    a manual `python -m quantstack.dashboard.server` run."""
    result = run_wire_selftest()
    assert isinstance(result["port"], int) and result["port"] > 0
    assert result["indexed_overwrite_ok"] is True
    assert set(result["hosted_tables"]) == {"positions", "equity", "fills", "meta"}
    assert len(result["positions_rows_read_back"]) == 2
    assert len(result["equity_rows_read_back"]) == 2
    assert result["float_bit_exact_ok"] is True
    assert result["foreign_origin_status"] == 403
    assert result["same_origin_status"] == 101
    assert result["origin_policy_ok"] is True


# --------------------------------------------------------------------------
# Origin policy (security finding: check_origin used to return True)
# --------------------------------------------------------------------------


def test_foreign_origin_is_rejected_same_origin_and_no_origin_accepted():
    """The upstream handler accepted any Origin, so any web page open in the
    user's browser could read or clear() the book. Now: foreign -> 403 (no
    session at all, so nothing can be read or cleared); same-origin and
    no-Origin (non-browser clients) -> accepted and able to read."""
    sink = PerspectiveSink()
    sink.update_positions([{"symbol": "AAPL", "qty": 969.0, "last": 125.67, "value": 121774.23}])
    with BackgroundDashboard(sink).start() as dash:
        same_origin = f"http://127.0.0.1:{dash.port}"
        assert _status(dash.ws_url, {"Origin": "https://evil.example.com"}) == 403
        assert _status(dash.ws_url, {"Origin": "null"}) == 403  # file:// or sandboxed iframe
        assert _status(dash.ws_url, {"Origin": f"http://127.0.0.1:{dash.port + 1}"}) == 403
        assert _status(dash.ws_url, {"Origin": same_origin}) == 101
        assert _status(dash.ws_url, {"Origin": f"http://localhost:{dash.port}",
                                     "Host": f"localhost:{dash.port}"}) == 101
        assert _status(dash.ws_url, {}) == 101
        # DNS rebinding: a hostile name re-pointed at 127.0.0.1 makes Origin
        # and Host agree -- still refused while bound to loopback.
        rebound = f"evil.example.com:{dash.port}"
        assert _status(dash.ws_url, {"Origin": f"http://{rebound}", "Host": rebound}) == 403

        read = _read(dash.ws_url, ["positions"], headers={"Origin": same_origin})
        assert read["positions"][0]["symbol"] == "AAPL"
    assert sink.positions.size() == 1  # the rejected clients changed nothing


def test_allow_origin_list_is_exact():
    sink = PerspectiveSink()
    with BackgroundDashboard(sink, allowed_origins=["HTTP://LocalHost:3000/"]).start() as dash:
        assert _status(dash.ws_url, {"Origin": "http://localhost:3000"}) == 101
        assert _status(dash.ws_url, {"Origin": "http://localhost:3001"}) == 403
        assert _status(dash.ws_url, {"Origin": "https://localhost:3000"}) == 403


def test_origin_allowed_unit_cases():
    assert origin_allowed("http://127.0.0.1:8080", "127.0.0.1:8080")
    assert origin_allowed("http://[::1]:8080", "[::1]:8080", bind_host="::1")
    assert not origin_allowed("http://127.0.0.1:8080", None)
    assert not origin_allowed("https://evil.example.com", "127.0.0.1:8080")
    assert not origin_allowed("http://evil.example.com:8080", "evil.example.com:8080")
    # an explicit, non-loopback bind: the user chose to expose it; same-origin suffices
    assert origin_allowed("http://dash.lan:8080", "dash.lan:8080", bind_host="0.0.0.0")
    assert not origin_allowed("http://other.lan:8080", "dash.lan:8080", bind_host="0.0.0.0")
    assert origin_allowed("http://x.test", "127.0.0.1:1", allowed_origins={"http://x.test"})
    with pytest.raises(ValueError):
        server_mod.normalise_origin("localhost:3000")  # no scheme


# --------------------------------------------------------------------------
# BackgroundDashboard: non-blocking serving for scripts/run_all.py
# --------------------------------------------------------------------------


def _http_get(url: str) -> tuple[int, str, bytes]:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=10) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), resp.read()


def test_background_dashboard_start_is_listening_and_stop_is_clean():
    sink = PerspectiveSink()
    dash = serve_in_background(sink)  # host 127.0.0.1, port 0
    try:
        assert dash.running
        assert dash.url == f"http://127.0.0.1:{dash.port}/"
        assert dash.ws_url == f"ws://127.0.0.1:{dash.port}/ws"
        socket.create_connection(("127.0.0.1", dash.port), timeout=2).close()
        status, ctype, body = _http_get(dash.url)
        assert status == 200 and ctype.startswith("text/html")
        assert b"<perspective-viewer" in body

        # an open websocket client must not keep stop() from finishing, and
        # must see the connection closed
        closed = threading.Event()
        opened = threading.Event()

        def client():
            async def run():
                conn = await tornado.websocket.websocket_connect(dash.ws_url)
                opened.set()
                while await conn.read_message() is not None:
                    pass
                closed.set()
                conn.close()  # else tornado warns "Unclosed WebSocketClientConnection" at GC
            asyncio.run(asyncio.wait_for(run(), 15))

        t = threading.Thread(target=client, daemon=True)
        t.start()
        assert opened.wait(5)
    finally:
        dash.stop(timeout=10)
    assert not dash.running
    assert closed.wait(5), "client never saw the server close its websocket"
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", dash.port), timeout=2)
    dash.stop()  # idempotent
    # the port is free again
    tornado.netutil.bind_sockets(dash.port, address="127.0.0.1")[0].close()


def test_background_dashboard_busy_port_raises_from_start():
    sock = tornado.netutil.bind_sockets(0, address="127.0.0.1", reuse_port=False)[0]
    try:
        busy = sock.getsockname()[1]
        with pytest.raises(OSError):
            BackgroundDashboard(PerspectiveSink(), port=busy).start()
    finally:
        sock.close()


# --------------------------------------------------------------------------
# index.html: pins, banner, local-asset mode
# --------------------------------------------------------------------------


class _AssetUrls(html.parser.HTMLParser):
    """script src / link href attributes plus inline-module import URLs."""

    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []
        self._in_script = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            self._in_script = True
            if attrs.get("src"):
                self.urls.append(attrs["src"])
        if tag == "link" and attrs.get("href"):
            self.urls.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = False

    def handle_data(self, data):
        if self._in_script:
            self.urls += re.findall(r"""(?:from|import)\s*\(?\s*["']([^"']+)["']""", data)


def test_index_html_pins_every_perspective_package_to_the_python_version():
    """The wasm wire protocol has to match between page and server: every
    @perspective-dev/* URL in the page must pin exactly
    perspective.__version__ (and the summary reports what the page pins,
    not what Python has)."""
    parser = _AssetUrls()
    parser.feed(server_mod.INDEX_HTML.read_text())
    urls = [u for u in parser.urls if "@perspective-dev/" in u]
    assert urls, "no @perspective-dev URLs found in index.html"
    packages = set()
    for url in urls:
        m = re.fullmatch(r"https://cdn\.jsdelivr\.net/npm/(@perspective-dev/[a-z0-9-]+)@([^/]+)/.+", url)
        assert m, f"unpinned or unexpected URL: {url}"
        assert m.group(2) == perspective.__version__, url
        packages.add(m.group(1))
    assert packages == {
        "@perspective-dev/client", "@perspective-dev/viewer",
        "@perspective-dev/viewer-datagrid", "@perspective-dev/viewer-charts",
    }
    pins = npm_pins_in_index_html()
    assert set(pins) == packages
    assert all(v == [perspective.__version__] for v in pins.values())


def test_npm_pins_reflect_the_html_not_the_python_version(tmp_path):
    page = tmp_path / "index.html"
    page.write_text(
        '<script src="https://cdn.jsdelivr.net/npm/@perspective-dev/client@9.9.9/dist/cdn/p.js"></script>'
        '<script>import x from "https://cdn.jsdelivr.net/npm/@perspective-dev/client@5.5.1/a.js"</script>'
    )
    assert npm_pins_in_index_html(page) == {"@perspective-dev/client": ["5.5.1", "9.9.9"]}


def test_index_html_has_a_demo_banner_driven_by_the_meta_table():
    page = server_mod.INDEX_HTML.read_text()
    assert re.search(r'<div id="demo-banner"[^>]*\bhidden\b', page)  # hidden by default
    assert 'open_table("meta")' in page
    assert 'meta.data_source === "demo"' in page


def _fake_npm_dir(root: Path, version: str) -> Path:
    for package in npm_pins_in_index_html():
        short = package.split("/", 1)[1]
        pkg = root / short / "package"
        (pkg / "dist" / "cdn").mkdir(parents=True)
        (pkg / "package.json").write_text(json.dumps({"name": package, "version": version}))
        (pkg / "dist" / "cdn" / "x.js").write_text("export default 1;")
        (pkg / "dist" / "cdn" / "x.wasm").write_bytes(b"\0asm\1\0\0\0")
    return root


def test_npm_dir_serves_pinned_packages_locally_and_checks_versions(tmp_path):
    npm = _fake_npm_dir(tmp_path / "npm", perspective.__version__)
    with BackgroundDashboard(PerspectiveSink(), npm_dir=npm).start() as dash:
        _, ctype, body = _http_get(dash.url)
        page = body.decode()
        assert ctype.startswith("text/html")
        assert "cdn.jsdelivr.net" not in page
        assert f'src="/npm/@perspective-dev/viewer@{perspective.__version__}/dist/cdn/' in page
        base = f"{dash.url}npm/@perspective-dev/client@{perspective.__version__}/dist/cdn/"
        assert _http_get(base + "x.js")[1].startswith("text/javascript")
        assert _http_get(base + "x.wasm")[1] == "application/wasm"
    with pytest.raises(ValueError, match="pins"):
        make_app(perspective.Server(), npm_dir=_fake_npm_dir(tmp_path / "old", "0.0.1"))
    with pytest.raises(FileNotFoundError):
        make_app(perspective.Server(), npm_dir=tmp_path / "empty")


# --------------------------------------------------------------------------
# Replay loading
# --------------------------------------------------------------------------


def test_equity_loader_delegates_to_contracts_reader(tmp_path, monkeypatch):
    eq = tmp_path / "eq.csv"
    eq.write_text("date,equity_hrp,equity_equal_engine\n2026-01-02,1.5,2.5\n2026-01-03,1.75,2.75\n")
    calls = []
    real = server_mod.read_equity_csv

    def spy(path, column=None):
        calls.append((Path(path), column))
        return real(path, column)

    monkeypatch.setattr(server_mod, "read_equity_csv", spy)
    rows, col = server_mod._load_equity_csv(eq)
    assert calls == [(eq, None)]
    assert col == "equity_hrp"  # first equity* column when there is no plain 'equity'
    assert rows == [{"date": "2026-01-02", "equity": 1.5}, {"date": "2026-01-03", "equity": 1.75}]
    rows, col = server_mod._load_equity_csv(eq, "equity_equal_engine")
    assert col == "equity_equal_engine" and rows[0]["equity"] == 2.5


# --------------------------------------------------------------------------
# CLI (every results path redirected into tmp_path)
# --------------------------------------------------------------------------


def _free_port() -> int:
    sock = tornado.netutil.bind_sockets(0, address="127.0.0.1")[0]
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture
def cli(tmp_path, monkeypatch):
    """Run server.main() with RESULTS_DIR and the default replay paths in
    tmp_path/results, and serve() patched out (past that point the CLI's job
    is just "block forever"). ``run(*argv, summary=path)`` returns the JSON
    the run wrote at ``path`` (default: the canonical summary)."""
    results = tmp_path / "results"
    results.mkdir()
    monkeypatch.setattr(server_mod, "RESULTS_DIR", results)
    monkeypatch.setattr(server_mod, "DEFAULT_EQUITY_CSV", results / "execution_equity.csv")
    monkeypatch.setattr(server_mod, "DEFAULT_POSITIONS_CSV", results / "execution_positions.csv")
    monkeypatch.setattr(server_mod, "DEFAULT_FILLS_CSV", results / "execution_fills.csv")
    served: dict = {}

    def fake_serve(sink, port, host="127.0.0.1", **kwargs):
        served.update(sink=sink, port=port, host=host, **kwargs)

    monkeypatch.setattr(server_mod, "serve", fake_serve)

    def run(*argv: str, summary: Path | None = None) -> dict:
        served.clear()
        assert server_mod.main(list(argv)) == 0
        path = summary if summary is not None else results / "dashboard_summary.json"
        return json.loads(Path(path).read_text())

    run.served = served
    run.results = results
    return run


def _write_replay(dirpath, equity_lines, with_fills: bool, positions="default", fills=None):
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / "eq.csv").write_text("date,equity_hrp\n" + "\n".join(equity_lines) + "\n")
    if positions == "default":
        positions = "as_of,symbol,qty,last,value\n2026-01-03,AAPL,10.0,101.25,1012.5\n"
    (dirpath / "pos.csv").write_text(positions)
    if with_fills or fills is not None:
        (dirpath / "execution_fills.csv").write_text(
            fills if fills is not None
            else "ts,symbol,side,qty,price\n2026-01-02T14:30:00,AAPL,BUY,10.0,101.25\n"
        )
    return dirpath / "eq.csv", dirpath / "pos.csv"


def _abs(p: Path) -> str:
    return str(p.resolve())


@pytest.mark.slow
def test_cli_main_writes_summary_and_serves(tmp_path, cli):
    """Full CLI path (argument parsing, demo-data fallback, self-test,
    summary write) minus the final infinite `serve()` call. Missing custom
    replay files: an ad-hoc run, so the summary goes next to them."""
    port = _free_port()
    missing = tmp_path / "missing"
    missing.mkdir()
    summary = cli(
        "--port", str(port),
        "--replay", str(missing / "no_such_equity.csv"), str(missing / "no_such_positions.csv"),
        "--allow-origin", "http://localhost:3000/",
        summary=missing / "dashboard_summary.json",
    )
    assert cli.served["port"] == port
    assert cli.served["allowed_origins"] == ["http://localhost:3000"]
    assert summary["summary_kind"] == "ad-hoc"
    assert summary["perspective_version"] == perspective.__version__
    assert summary["replay"]["is_demo"] is True
    assert summary["replay"]["fallback_reason"].startswith("not found")
    assert summary["replay"]["meta_table"]["data_source"] == "demo"
    assert cli.served["sink"].get_meta()["data_source"] == "demo"
    assert summary["wire_selftest"]["measured_this_run"] is True
    assert summary["wire_selftest"]["indexed_update_overwrote_in_place"] is True
    assert summary["wire_selftest"]["float_round_trip_bit_exact"] is True
    assert summary["wire_selftest"]["foreign_origin_handshake"]["http_status"] == 403
    assert summary["wire_selftest"]["origin_policy_enforced"] is True
    assert set(summary["tables"]) == {"positions", "equity", "fills", "meta"}
    assert summary["replay"]["table_sizes_after_load"] == {"positions": 3, "equity": 15, "fills": 3}
    npm = summary["npm_packages_used_by_static_index_html"]
    assert npm["source_file"] == "quantstack/dashboard/static/index.html"  # repo-relative
    assert npm["@perspective-dev/viewer"] == perspective.__version__
    assert npm["all_pinned_to_perspective_python"] is True
    assert not (cli.results / "dashboard_summary.json").exists()  # canonical untouched


def test_cli_once_replays_selftests_summarises_and_does_not_serve(tmp_path, cli):
    """--once on the default inputs is the canonical run `make all` uses: it
    writes results/dashboard_summary.json with measured wire evidence and
    returns 0 without serving -- even if --port is busy."""
    _write_replay(cli.results, ["2026-01-02,1000.5", "2026-01-03,1001.75"], True)
    (cli.results / "eq.csv").rename(cli.results / "execution_equity.csv")
    (cli.results / "pos.csv").rename(cli.results / "execution_positions.csv")
    sock = tornado.netutil.bind_sockets(0, address="127.0.0.1")[0]
    try:
        summary = cli("--once", "--port", str(sock.getsockname()[1]))
    finally:
        sock.close()
    assert cli.served == {}  # serve() never called
    assert summary["summary_kind"] == "canonical"
    assert summary["wire_selftest"]["measured_this_run"] is True
    assert summary["replay"]["is_demo"] is False
    assert summary["replay"]["n_fills"] == 1
    assert summary["replay"]["equity_columns_available"] == ["equity_hrp"]
    assert summary["replay"]["meta_table"]["data_source"] == "replay"


def test_cli_once_exits_zero_as_a_subprocess(tmp_path):
    eq, pos = _write_replay(tmp_path / "run", ["2026-01-02,1000.5"], True)
    out = tmp_path / "summary.json"
    proc = subprocess.run(
        [sys.executable, "-m", "quantstack.dashboard.server", "--once",
         "--replay", str(eq), str(pos), "--summary", str(out)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    assert proc.returncode == 0, proc.stderr
    assert "--once: not serving" in proc.stdout
    summary = json.loads(out.read_text())
    assert summary["wire_selftest"]["measured_this_run"] is True
    assert summary["replay"]["n_fills"] == 1


def test_cli_custom_replay_never_borrows_another_runs_fills(tmp_path, cli):
    """A custom --replay whose directory has no execution_fills.csv loads *no*
    fills (it used to silently load results/execution_fills.csv, mixing
    sources); an explicit --fills or a sibling file is honoured and
    recorded. Ad-hoc summaries land next to the replayed files."""
    eq, pos = _write_replay(tmp_path / "run_a", ["2026-01-02,1000.5", "2026-01-03,1001.75"], False)
    summary = cli("--port", str(_free_port()), "--no-selftest", "--replay", str(eq), str(pos),
                  summary=tmp_path / "run_a" / "dashboard_summary.json")
    assert summary["replay"]["is_demo"] is False
    assert summary["replay"]["fills_csv"] is None
    assert summary["replay"]["n_fills"] == 0
    assert cli.served["sink"].fills.size() == 0

    eq, pos = _write_replay(tmp_path / "run_b", ["2026-01-02,1000.5"], True)
    summary = cli("--port", str(_free_port()), "--no-selftest", "--replay", str(eq), str(pos),
                  summary=tmp_path / "run_b" / "dashboard_summary.json")
    assert summary["replay"]["fills_csv"] == _abs(tmp_path / "run_b" / "execution_fills.csv")
    assert cli.served["sink"].fills.size() == 1

    out = tmp_path / "explicit.json"
    summary = cli(
        "--port", str(_free_port()), "--no-selftest",
        "--replay", str(tmp_path / "run_a" / "eq.csv"), str(tmp_path / "run_a" / "pos.csv"),
        "--fills", str(tmp_path / "run_b" / "execution_fills.csv"),
        "--summary", str(out),
        summary=out,
    )
    assert summary["replay"]["fills_csv"] == _abs(tmp_path / "run_b" / "execution_fills.csv")
    assert summary["replay"]["n_fills"] == 1
    assert not (cli.results / "dashboard_summary.json").exists()


@pytest.mark.parametrize(
    "fills, needle",
    [
        ("ts,symbol,side,qty,price\n2026-01-02T14:30:00,AAPL,BUY,ten,101.25\n", "'qty'"),
        ("ts,symbol,side,qty\n2026-01-02T14:30:00,AAPL,BUY,10.0\n", "'price'"),
        ("", "EmptyDataError"),
    ],
    ids=["non-numeric-qty", "missing-column", "empty-file"],
)
def test_cli_bad_fills_are_skipped_with_a_warning_not_a_crash(tmp_path, cli, fills, needle):
    """Fills used to sit outside the degrade-don't-crash guard: a bad qty or
    a missing column crashed main() after 'replaying ...'. Now the fills are
    skipped, the reason is recorded, and equity/positions are still served."""
    eq, pos = _write_replay(tmp_path / "run", ["2026-01-02,1000.5"], False, fills=fills)
    summary = cli("--port", str(_free_port()), "--no-selftest", "--replay", str(eq), str(pos),
                  summary=tmp_path / "run" / "dashboard_summary.json")
    replay = summary["replay"]
    assert replay["is_demo"] is False
    assert replay["n_fills"] == 0 and replay["fills_csv"] is None
    assert replay["fills_warning"].startswith("skipped fills from ")
    assert needle in replay["fills_warning"]
    assert replay["table_sizes_after_load"] == {"positions": 1, "equity": 1, "fills": 0}
    assert cli.served["sink"].get_meta()["data_source"] == "replay"


def test_cli_header_only_positions_is_a_flat_book_not_demo(tmp_path, cli):
    eq, pos = _write_replay(tmp_path / "run", ["2026-01-02,1000.5", "2026-01-03,1001.0"], False,
                            positions="as_of,symbol,qty,last,value,cash\n")
    summary = cli("--port", str(_free_port()), "--no-selftest", "--replay", str(eq), str(pos),
                  summary=tmp_path / "run" / "dashboard_summary.json")
    replay = summary["replay"]
    assert replay["is_demo"] is False and replay["fallback_reason"] is None
    assert replay["positions_flat_book"] is True
    assert replay["table_sizes_after_load"] == {"positions": 0, "equity": 2, "fills": 0}
    assert "flat book" in cli.served["sink"].get_meta()["note"]

    # a 0-byte positions file is a writer mid-write, not a flat book
    (tmp_path / "run" / "pos.csv").write_text("")
    summary = cli("--port", str(_free_port()), "--no-selftest", "--replay", str(eq), str(pos),
                  summary=tmp_path / "run" / "dashboard_summary.json")
    assert summary["replay"]["is_demo"] is True


def test_cli_equity_column_flag_and_unknown_column(tmp_path, cli):
    d = tmp_path / "run"
    _write_replay(d, [], False)
    (d / "eq.csv").write_text("date,equity_hrp,equity_equal_engine\n2026-01-02,1.5,2.5\n")
    summary = cli("--port", str(_free_port()), "--no-selftest", "--replay", str(d / "eq.csv"),
                  str(d / "pos.csv"), "--equity-column", "equity_equal_engine",
                  summary=d / "dashboard_summary.json")
    assert summary["replay"]["equity_source_column"] == "equity_equal_engine"
    assert summary["replay"]["equity_columns_available"] == ["equity_hrp", "equity_equal_engine"]
    assert cli.served["sink"].equity.view().to_records() == [{"date": "2026-01-02", "equity": 2.5}]

    summary = cli("--port", str(_free_port()), "--no-selftest", "--replay", str(d / "eq.csv"),
                  str(d / "pos.csv"), "--equity-column", "equity_nope",
                  summary=d / "dashboard_summary.json")
    assert summary["replay"]["is_demo"] is True
    assert "equity_nope" in summary["replay"]["fallback_reason"]


def test_cli_blank_equity_cell_is_served_not_dropped(tmp_path, cli):
    """One blank cell used to make the whole equity table empty while the
    summary still claimed 3 points. Now the row is served (as null) and the
    summary reports the table sizes actually served."""
    eq, pos = _write_replay(tmp_path / "run", ["2026-01-02,1000.5", "2026-01-03,", "2026-01-04,1002.0"], False)
    summary = cli("--port", str(_free_port()), "--no-selftest", "--replay", str(eq), str(pos),
                  summary=tmp_path / "run" / "dashboard_summary.json")
    assert summary["replay"]["n_equity_points"] == 3
    assert summary["replay"]["table_sizes_after_load"]["equity"] == 3
    assert summary["replay"]["table_size_warnings"] == []


def test_cli_no_selftest_keeps_previous_wire_evidence_without_touching_canonical(tmp_path, cli):
    """--no-selftest must not overwrite the websocket evidence with nulls,
    and (being ad-hoc) must not rewrite the canonical summary at all."""
    previous = {
        "wire_selftest": {
            "port_used": 43210,
            "measured_this_run": True,
            "positions_rows_read_back_over_websocket": [{"symbol": "AAPL"}],
            "indexed_update_overwrote_in_place": True,
        }
    }
    canonical = cli.results / "dashboard_summary.json"
    canonical.write_text(json.dumps(previous))
    eq, pos = _write_replay(tmp_path / "run", ["2026-01-02,1000.5"], False)
    summary = cli("--port", str(_free_port()), "--no-selftest", "--replay", str(eq), str(pos),
                  summary=tmp_path / "run" / "dashboard_summary.json")
    wire = summary["wire_selftest"]
    assert wire["port_used"] == 43210
    assert wire["indexed_update_overwrote_in_place"] is True
    assert wire["positions_rows_read_back_over_websocket"] == [{"symbol": "AAPL"}]
    assert wire["measured_this_run"] is False
    assert json.loads(canonical.read_text()) == previous  # untouched


def test_cli_no_selftest_on_default_inputs_writes_the_adhoc_file(tmp_path, cli):
    """The replayed files *are* in results/, so 'next to them' would be the
    canonical file: an ad-hoc run writes dashboard_summary.adhoc.json."""
    canonical = cli.results / "dashboard_summary.json"
    canonical.write_text("{}")
    summary = cli("--port", str(_free_port()), "--no-selftest",
                  summary=cli.results / "dashboard_summary.adhoc.json")
    assert summary["summary_kind"] == "ad-hoc"
    assert summary["replay"]["is_demo"] is True  # nothing in tmp results/
    assert canonical.read_text() == "{}"


def test_summary_paths_are_repo_relative():
    assert server_mod._rel(REPO_ROOT / "results" / "execution_equity.csv") == "results/execution_equity.csv"
    outside = Path("/definitely/not/in/the/repo.csv")
    assert server_mod._rel(outside) == str(outside)  # no relative form exists
    assert server_mod._scrub(f"not found: {REPO_ROOT}{os.sep}results/x.csv") == "not found: results/x.csv"


def test_cli_rejects_a_malformed_allow_origin(cli):
    with pytest.raises(SystemExit) as excinfo:
        cli("--once", "--allow-origin", "localhost:3000")
    assert excinfo.value.code == 2


def test_cli_port_in_use_fails_fast_before_writing_summary(tmp_path, cli):
    sock = tornado.netutil.bind_sockets(0, address="127.0.0.1")[0]
    try:
        busy = sock.getsockname()[1]
        with pytest.raises(SystemExit) as excinfo:
            cli("--port", str(busy), "--no-selftest")
        assert excinfo.value.code == 2
    finally:
        sock.close()
    assert not any(cli.results.glob("dashboard_summary*.json"))
    assert "sink" not in cli.served


# --------------------------------------------------------------------------
# Real browser (slow; skipped without Chromium or the page's JavaScript)
# --------------------------------------------------------------------------


def _screenshot_module():
    path = REPO_ROOT / "scripts" / "dashboard_screenshot.py"
    spec = importlib.util.spec_from_file_location("dashboard_screenshot", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.slow
def test_browser_connects_and_shows_the_demo_banner(tmp_path):
    """Drives the pre-installed Chromium over the DevTools protocol via
    scripts/dashboard_screenshot.py. Needs the pinned JS: set
    QUANTSTACK_NPM_DIR to unpacked npm packages, or have them in the
    script's download cache, or a reachable CDN; never downloads here."""
    shot = _screenshot_module()
    if shot.find_chromium() is None:
        pytest.skip("no Chromium/Chrome binary")
    npm_dir = os.environ.get("QUANTSTACK_NPM_DIR")
    if npm_dir is None and shot.default_npm_cache().is_dir():
        npm_dir = str(shot.default_npm_cache())
    try:
        local = shot.resolve_npm_dir("local", npm_dir) if npm_dir else None
    except shot.AssetsUnavailable as exc:
        pytest.skip(str(exc))
    if local is None and not shot.cdn_reachable():
        pytest.skip("no local npm packages (QUANTSTACK_NPM_DIR) and no CDN")
    result = shot.capture(
        tmp_path / "shot.png", demo=True,
        js_source="cdn" if local is None else "local", npm_dir=local,
        profile_dir=tmp_path / "profile", wait_s=120,
    )
    assert result["connected"], result
    assert result["banner_visible"] is True
    assert result["flush"] == "ok" and result["viewers"] == 2
    assert (tmp_path / "shot.png").stat().st_size > 10_000
