"""Tests for quantstack.dashboard.server.

The whole point of this module (per the article) is that the display wire is
*real*: a Perspective ``Table`` living in one Python object gets read back
through an actual websocket, not a mock. So the main test here does exactly
that end to end:

  1. start the real Tornado app (``make_app``) on an OS-assigned free port,
     in a background thread running its own asyncio/Tornado event loop;
  2. push rows into a :class:`PerspectiveSink` from the main thread/loop
     (including a second update to the same symbol, to prove the indexed
     table overwrites in place rather than appending);
  3. from the main thread, open a *second*, independent asyncio loop
     (``asyncio.run``) and connect an actual websocket client --
     ``tornado.websocket.websocket_connect`` paired with
     ``perspective.AsyncClient`` -- across a real loopback TCP socket to
     ``/ws``, then read the tables back with ``open_table(...).view()``.

No mocking of the wire was needed: ``websocket-client`` (the package used by
perspective's own ``tests/async/test_websocket_client.py``) isn't installed
here, but Tornado already ships an async websocket client
(``tornado.websocket.websocket_connect``), which is a fully real
alternative -- see the "Version-skew note" in
``quantstack/dashboard/server.py``'s module docstring for how that client
API was confirmed against the *installed* perspective-python 5.5.1, not
guessed from possibly-stale docs.

These run in well under a minute: the heaviest thing here is starting one
Tornado server thread and doing a handful of websocket round-trips.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import math
import random
import threading

import numpy as np
import perspective
import pytest
import tornado.httpserver
import tornado.ioloop
import tornado.netutil
import tornado.websocket

from quantstack.contracts import (
    EQUITY_SCHEMA,
    FILLS_SCHEMA,
    POSITIONS_SCHEMA,
    RecordingSink,
)
from quantstack.dashboard.server import PerspectiveSink, make_app, run_wire_selftest


# --------------------------------------------------------------------------
# PerspectiveSink in isolation (no network) -- schema + in-place update
# --------------------------------------------------------------------------


def test_sink_creates_tables_matching_contracts_schema():
    sink = PerspectiveSink()
    assert sink.positions.schema() == dict(POSITIONS_SCHEMA)
    assert sink.equity.schema() == dict(EQUITY_SCHEMA)
    assert sink.fills.schema() == dict(FILLS_SCHEMA)
    assert sink.positions.get_index() == "symbol"
    assert sink.equity.get_index() == "date"
    assert sink.fills.get_index() is None


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


class _BackgroundServer:
    """Runs make_app(server) on a free port in a background thread with its
    own asyncio/Tornado event loop -- exactly the shape asked for: the
    server side must be a genuinely separate loop from the test's client
    side, connected only by a loopback TCP socket."""

    def __init__(self, server: "perspective.Server", host: str = "127.0.0.1") -> None:
        self.host = host
        self._app = make_app(server)
        self._sockets = tornado.netutil.bind_sockets(0, address=host)
        self.port = self._sockets[0].getsockname()[1]
        self._ready = threading.Event()
        self.io_loop: tornado.ioloop.IOLoop | None = None
        self._http_server: tornado.httpserver.HTTPServer | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.io_loop = tornado.ioloop.IOLoop.current()
        self._http_server = tornado.httpserver.HTTPServer(self._app)
        self._http_server.add_sockets(self._sockets)
        self.io_loop.add_callback(self._ready.set)
        self.io_loop.start()

    def start(self, timeout: float = 10.0) -> None:
        self._thread.start()
        if not self._ready.wait(timeout=timeout):
            raise RuntimeError("background dashboard server did not start in time")

    def stop(self, timeout: float = 10.0) -> None:
        assert self.io_loop is not None and self._http_server is not None
        self.io_loop.add_callback(self._http_server.stop)
        self.io_loop.add_callback(self.io_loop.stop)
        self._thread.join(timeout=timeout)


async def _read_tables_over_websocket(host: str, port: int, table_names: list[str]) -> dict:
    """Connect a real websocket client to the running server and read each
    named table back with view().to_records(). Mirrors the pattern in the
    installed perspective package's own
    perspective/tests/async/test_websocket_client.py and
    perspective/tests/async/test_async_client.py: an AsyncClient whose
    `handle_request` callback writes bytes to the socket, fed incoming bytes
    via `handle_response` from the websocket's on_message callback."""
    client_holder: dict = {}
    loop = asyncio.get_running_loop()

    def on_message(msg):
        if msg is None:  # connection closed
            return
        loop.create_task(client_holder["client"].handle_response(msg))

    conn = await tornado.websocket.websocket_connect(
        f"ws://{host}:{port}/ws", on_message_callback=on_message
    )

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


def test_websocket_wire_reads_back_pushed_rows_with_indexed_overwrite():
    server = perspective.Server()
    sink = PerspectiveSink(server=server)
    bg = _BackgroundServer(server)
    bg.start()
    try:
        # Two writes to the same symbol: the *second* value must be the one
        # that comes back over the wire, and there must still be one row.
        sink.update_positions([{"symbol": "AAPL", "qty": 10.0, "last": 100.0, "value": 1000.0}])
        sink.update_positions([{"symbol": "AAPL", "qty": 40.0, "last": 102.0, "value": 4080.0}])
        sink.update_positions([{"symbol": "MSFT", "qty": 5.0, "last": 400.0, "value": 2000.0}])
        sink.update_equity([{"date": "2026-09-24", "equity": 1_000_000.0}])
        sink.update_equity([{"date": "2026-09-25", "equity": 1_006_000.0}])

        result = asyncio.run(
            asyncio.wait_for(
                _read_tables_over_websocket(bg.host, bg.port, ["positions", "equity"]),
                timeout=10.0,
            )
        )
    finally:
        bg.stop()

    assert set(result["hosted_tables"]) >= {"positions", "equity", "fills"}

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
    assert set(result["hosted_tables"]) == {"positions", "equity", "fills"}
    assert len(result["positions_rows_read_back"]) == 2
    assert len(result["equity_rows_read_back"]) == 2
    assert result["float_bit_exact_ok"] is True


def _free_port() -> int:
    sock = tornado.netutil.bind_sockets(0, address="127.0.0.1")[0]
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture
def cli(tmp_path, monkeypatch):
    """Run server.main() with RESULTS_DIR in tmp_path and serve() patched
    out (past that point the CLI's job is just "block forever")."""
    import quantstack.dashboard.server as server_mod

    monkeypatch.setattr(server_mod, "RESULTS_DIR", tmp_path)
    served: dict = {}

    def fake_serve(sink, port, host="127.0.0.1"):
        served.update(sink=sink, port=port, host=host)

    monkeypatch.setattr(server_mod, "serve", fake_serve)

    def run(*argv: str) -> dict:
        server_mod.main(list(argv))
        return json.loads((tmp_path / "dashboard_summary.json").read_text())

    run.served = served
    return run


def _write_replay(dirpath, equity_lines, with_fills: bool):
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / "eq.csv").write_text("date,equity_hrp\n" + "\n".join(equity_lines) + "\n")
    (dirpath / "pos.csv").write_text(
        "as_of,symbol,qty,last,value\n2026-01-03,AAPL,10.0,101.25,1012.5\n"
    )
    if with_fills:
        (dirpath / "execution_fills.csv").write_text(
            "ts,symbol,side,qty,price\n2026-01-02T14:30:00,AAPL,BUY,10.0,101.25\n"
        )
    return dirpath / "eq.csv", dirpath / "pos.csv"


@pytest.mark.slow
def test_cli_main_writes_summary_and_serves(tmp_path, cli):
    """Full CLI path (argument parsing, demo-data fallback, self-test,
    summary write) minus the final infinite `serve()` call."""
    port = _free_port()
    summary = cli(
        "--port", str(port),
        "--replay", str(tmp_path / "no_such_equity.csv"), str(tmp_path / "no_such_positions.csv"),
    )
    assert cli.served["port"] == port
    assert summary["perspective_version"] == perspective.__version__
    assert summary["replay"]["is_demo"] is True
    assert summary["replay"]["fallback_reason"].startswith("not found")
    assert summary["wire_selftest"]["measured_this_run"] is True
    assert summary["wire_selftest"]["indexed_update_overwrote_in_place"] is True
    assert summary["wire_selftest"]["float_round_trip_bit_exact"] is True
    assert set(summary["tables"]) == {"positions", "equity", "fills"}
    assert summary["replay"]["table_sizes_after_load"] == {"positions": 3, "equity": 15, "fills": 3}


def test_cli_custom_replay_never_borrows_another_runs_fills(tmp_path, cli):
    """A custom --replay whose directory has no execution_fills.csv loads *no*
    fills (it used to silently load results/execution_fills.csv, mixing
    sources); an explicit --fills or a sibling file is honoured and
    recorded."""
    eq, pos = _write_replay(tmp_path / "run_a", ["2026-01-02,1000.5", "2026-01-03,1001.75"], False)
    summary = cli("--port", str(_free_port()), "--no-selftest", "--replay", str(eq), str(pos))
    assert summary["replay"]["is_demo"] is False
    assert summary["replay"]["fills_csv"] is None
    assert summary["replay"]["n_fills"] == 0
    assert cli.served["sink"].fills.size() == 0

    eq, pos = _write_replay(tmp_path / "run_b", ["2026-01-02,1000.5"], True)
    summary = cli("--port", str(_free_port()), "--no-selftest", "--replay", str(eq), str(pos))
    assert summary["replay"]["fills_csv"] == str(tmp_path / "run_b" / "execution_fills.csv")
    assert cli.served["sink"].fills.size() == 1

    summary = cli(
        "--port", str(_free_port()), "--no-selftest",
        "--replay", str(tmp_path / "run_a" / "eq.csv"), str(tmp_path / "run_a" / "pos.csv"),
        "--fills", str(tmp_path / "run_b" / "execution_fills.csv"),
    )
    assert summary["replay"]["fills_csv"] == str(tmp_path / "run_b" / "execution_fills.csv")
    assert summary["replay"]["n_fills"] == 1


def test_cli_blank_equity_cell_is_served_not_dropped(tmp_path, cli):
    """One blank cell used to make the whole equity table empty while the
    summary still claimed 3 points. Now the row is served (as null) and the
    summary reports the table sizes actually served."""
    eq, pos = _write_replay(tmp_path / "run", ["2026-01-02,1000.5", "2026-01-03,", "2026-01-04,1002.0"], False)
    summary = cli("--port", str(_free_port()), "--no-selftest", "--replay", str(eq), str(pos))
    assert summary["replay"]["n_equity_points"] == 3
    assert summary["replay"]["table_sizes_after_load"]["equity"] == 3
    assert summary["replay"]["table_size_warnings"] == []


def test_cli_no_selftest_keeps_previous_wire_evidence(tmp_path, cli):
    """--no-selftest must not overwrite the websocket evidence with nulls."""
    previous = {
        "wire_selftest": {
            "port_used": 43210,
            "measured_this_run": True,
            "positions_rows_read_back_over_websocket": [{"symbol": "AAPL"}],
            "indexed_update_overwrote_in_place": True,
        }
    }
    (tmp_path / "dashboard_summary.json").write_text(json.dumps(previous))
    eq, pos = _write_replay(tmp_path / "run", ["2026-01-02,1000.5"], False)
    summary = cli("--port", str(_free_port()), "--no-selftest", "--replay", str(eq), str(pos))
    wire = summary["wire_selftest"]
    assert wire["port_used"] == 43210
    assert wire["indexed_update_overwrote_in_place"] is True
    assert wire["positions_rows_read_back_over_websocket"] == [{"symbol": "AAPL"}]
    assert wire["measured_this_run"] is False


def test_cli_port_in_use_fails_fast_before_writing_summary(tmp_path, cli):
    sock = tornado.netutil.bind_sockets(0, address="127.0.0.1")[0]
    try:
        busy = sock.getsockname()[1]
        with pytest.raises(SystemExit) as excinfo:
            cli("--port", str(busy), "--no-selftest")
        assert excinfo.value.code == 2
    finally:
        sock.close()
    assert not (tmp_path / "dashboard_summary.json").exists()
    assert "sink" not in cli.served
