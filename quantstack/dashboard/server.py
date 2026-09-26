"""``quantstack.dashboard`` -- the display layer: State -> Screen (contract 4).

This module wires ``contracts.DashboardSink`` up to a real Perspective server
(perspective-python 5.5.1) plus a Tornado websocket handler, and serves the
``<perspective-viewer>`` page that renders it.  The point of the exercise
(per the article "Five Repos, One Engine") is that this is the *one* wire in
the whole stack you can actually watch on a network tab: bytes really cross a
loopback socket between the Python ``Table`` and the browser (or, in our
test, a second in-process Python client standing in for the browser).

Entry points: :class:`PerspectiveSink` (the ``DashboardSink``),
:func:`make_app` (the Tornado app), :func:`serve` (blocking, the CLI's main
loop), :class:`BackgroundDashboard` / :func:`serve_in_background`
(non-blocking: a daemon thread with its own asyncio loop, for scripts such as
``scripts/run_all.py`` and ``scripts/dashboard_screenshot.py``) and
:func:`main` (``python -m quantstack.dashboard.server``; ``--once`` replays,
self-tests and writes the summary without serving).

SECURITY -- READ BEFORE DEPLOYING
=================================
``perspective.handlers.tornado.PerspectiveTornadoHandler`` is, in its own
docstring, "a reference integration with **no authentication,
authorization, origin enforcement, or rate limiting**, and is not safe to
expose to untrusted networks"; it also overrides ``check_origin`` to accept
every origin.  Anyone whose websocket is accepted on ``/ws`` can read *and
write* (``update``/``clear``/``delete``) every table this process hosts.
What this module adds, and what it does not:

* **No authentication, still.**  Any process that can reach the port can
  connect: non-browser clients send no ``Origin`` header and are accepted
  (this is Tornado's rule, and how the self-test and the tests connect).
* **Same-origin only for browsers.**  :class:`OriginCheckedPerspectiveHandler`
  replaces the accept-everything ``check_origin``: a websocket that carries an
  ``Origin`` header is accepted only if that origin's ``host:port`` equals the
  request's ``Host`` header (i.e. the page was served by this server), or if
  it is listed explicitly via ``--allow-origin`` / ``allowed_origins=``
  (exact ``scheme://host[:port]`` match).  Anything else gets HTTP 403, so a
  web page open in your browser (``https://evil.example.com``) can no longer
  read or ``clear()`` the book over ``ws://127.0.0.1:PORT/ws``.
* **DNS-rebinding guard.**  When bound to a loopback address (the default),
  a same-origin request is additionally required to name a loopback host
  (``localhost``, ``127.0.0.1``, ``::1`` or the bound address); otherwise a
  hostile domain re-pointed at 127.0.0.1 would count as "same origin".
* **Localhost by default.**  :func:`serve`, :class:`BackgroundDashboard` and
  the CLI all default ``--host`` to ``127.0.0.1``.  Binding to ``0.0.0.0``
  (or any non-loopback address) requires passing it explicitly and prints a
  warning.  Do not put this behind a reverse proxy on a shared network
  without adding your own auth layer in front of it.

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

   ``static/index.html`` uses these exact URLs; the summary JSON reports the
   pins actually found in that file (:func:`npm_pins_in_index_html`) and a
   test fails if any of them drifts from ``perspective.__version__``.
   Offline / no-CDN use: ``--npm-dir DIR`` (``npm_dir=``) serves the same
   pinned packages from unpacked npm tarballs (``DIR/<name>/package/...``,
   e.g. ``DIR/client/package/dist/cdn/perspective.js``) and rewrites only the
   jsdelivr prefix of the page; the package versions are checked against
   the page's pins.

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
   by ``scripts/dashboard_screenshot.py`` -- playwright's Python package is
   not installed and was not added): without the wait the page shows
   ``connection failed: Error: Missing perspective-client.wasm``; with it
   both viewers render the replayed tables
   (``results/figures/dashboard_screenshot.png``, produced with
   ``--npm-dir`` because this sandbox cannot reach jsdelivr).

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
import ipaddress
import json
import logging
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping
from urllib.parse import urlsplit

import numpy as np
import pandas as pd
import perspective
import pyarrow as pa
import tornado.httpclient
import tornado.httpserver
import tornado.ioloop
import tornado.netutil
import tornado.web
import tornado.websocket
from perspective.handlers.tornado import PerspectiveTornadoHandler

from quantstack.contracts import (
    EQUITY_SCHEMA,
    FILLS_SCHEMA,
    POSITIONS_SCHEMA,
    equity_csv_columns,
    read_equity_csv,
    read_positions_csv,
)

log = logging.getLogger("quantstack.dashboard")

STATIC_DIR = Path(__file__).parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"
REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"
DEFAULT_EQUITY_CSV = RESULTS_DIR / "execution_equity.csv"
DEFAULT_POSITIONS_CSV = RESULTS_DIR / "execution_positions.csv"
DEFAULT_FILLS_CSV = RESULTS_DIR / "execution_fills.csv"
FILLS_CSV_NAME = DEFAULT_FILLS_CSV.name
SUMMARY_NAME = "dashboard_summary.json"
# Where an ad-hoc run's summary goes when "next to the replayed files" would
# be the canonical results/dashboard_summary.json itself.
ADHOC_SUMMARY_NAME = "dashboard_summary.adhoc.json"

TABLE_NAMES = ("positions", "equity", "fills")  # the contract-4 data tables
# A tiny key/value table the page reads to label its data source (and to show
# a DEMO DATA banner). Not part of contract 4; hosted next to the data tables.
META_TABLE_NAME = "meta"
META_SCHEMA = {"key": "string", "value": "string"}
HOSTED_TABLE_NAMES = TABLE_NAMES + (META_TABLE_NAME,)

# Tornado's default cap on an *incoming* websocket message is 10 MiB. Browser
# requests are tiny, but a client that uploads a table (the handler lets any
# accepted client write -- see the security section) or a future bulk replay
# would hit it, and perspective's handler docstring warns about large
# datasets. 64 MiB is ample for this project's data (1760 equity rows, 573
# fills).
DEFAULT_WEBSOCKET_MAX_MESSAGE_SIZE = 64 * 1024 * 1024

LOOPBACK_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1"})

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
    if isinstance(value, np.datetime64):
        value = pd.Timestamp(value)
    if isinstance(value, _dt.date):  # date, datetime, pd.Timestamp
        return value.isoformat()
    return str(value)


_ISO_DATE_PREFIX = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})(?:[T ]|\s*$)")


def _coerce_date_key(value) -> str | None:
    """The equity table's ``date`` key: always ``'YYYY-MM-DD'``.

    ``datetime.date``, ``datetime.datetime``, ``pd.Timestamp`` and
    ``np.datetime64`` are reduced to their calendar day, and so is a string
    that *starts* with an ISO date (``'2026-01-05T00:00:00'``,
    ``'2026-01-05 16:00'``). Without this ``pd.Timestamp('2026-01-05')``
    (``isoformat()`` -> ``'2026-01-05T00:00:00'``) and
    ``date(2026, 1, 5)`` (``'2026-01-05'``) were two index keys, so one day
    could appear twice on the curve. Any other string is kept verbatim.
    """
    if _is_missing(value):
        return None
    if isinstance(value, np.datetime64):
        value = pd.Timestamp(value)
    if isinstance(value, _dt.date):
        return value.isoformat()[:10]
    text = value if isinstance(value, str) else str(value)
    match = _ISO_DATE_PREFIX.match(text)
    return match.group(1) if match else text


_COERCERS = {
    "float": (_coerce_float, pa.float64()),
    "string": (_coerce_string, pa.string()),
}


def _rows_to_arrow_ipc(
    rows: list[Mapping],
    schema: Mapping[str, str],
    index: str | None,
    date_keys: Iterable[str] = (),
) -> bytes:
    """Encode ``rows`` as an Arrow IPC stream typed by ``schema``.

    * Every schema column is sent for every row: a key missing from a row
      (or None / NaN) is null in that cell.  For an indexed table that means
      a row *replaces* the stored row for its key -- exactly what
      ``RecordingSink`` does (``positions[symbol] = dict(r)``); there is no
      merge with the previous row, whatever else is in the batch.
    * Keys that are not schema columns are ignored (the screen has no column
      for them).
    * Indexed tables require the index key on every row, mirroring
      ``RecordingSink`` (which raises ``KeyError`` on ``r["symbol"]``).
    * ``date_keys`` columns go through :func:`_coerce_date_key`.
    * A value that cannot be coerced raises ``ValueError`` naming the column
      and row; nothing is sent in that case.
    """
    if index is not None:
        for r in rows:
            if index not in r:
                raise KeyError(index)
    if not any(c in r for r in rows for c in schema):
        raise ValueError(
            f"none of the rows carry any schema column {list(schema)}; "
            f"got keys {sorted({str(k) for r in rows for k in r})}"
        )
    date_keys = set(date_keys)
    arrays, fields = [], []
    for col, col_type in schema.items():
        try:
            coerce, arrow_type = _COERCERS[col_type]
        except KeyError:  # contracts only uses float/string today
            raise ValueError(f"unsupported schema type {col_type!r} for {col!r}") from None
        if col in date_keys:
            coerce = _coerce_date_key
        values = []
        for i, r in enumerate(rows):
            value = r.get(col)
            try:
                values.append(coerce(value))
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(
                    f"row {i}: column {col!r} ({col_type}): cannot use {value!r} ({exc})"
                ) from exc
        arrays.append(pa.array(values, type=arrow_type))
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
      Date-like keys are normalised to ``'YYYY-MM-DD'`` (see
      :func:`_coerce_date_key`) so one day is always one row.
    * ``fills``     -- no index: every ``update()`` call appends new rows,
      because a fill blotter is a log, not a snapshot.

    Plus a small ``meta`` key/value table (:meth:`set_meta`) the page reads
    to label where the data came from; ``data_source="demo"`` makes it show
    a DEMO DATA banner.

    Row semantics are whole-row, like ``RecordingSink``: every schema column
    is written for every row, so a *partial* row (say only ``symbol`` and
    ``qty``) nulls the cells it does not mention -- it does not keep the
    previous ``last``/``value``, and the outcome does not depend on what else
    is in the batch.  Keys outside the schema are ignored.

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
        clash = sorted(set(HOSTED_TABLE_NAMES) & set(self.client.get_hosted_table_names()))
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
        self.meta = self.client.table(
            dict(META_SCHEMA), index="key", name=META_TABLE_NAME
        )

    @staticmethod
    def _push(table, rows: Iterable[Mapping], schema, index: str | None, date_keys=()) -> None:
        rows = [dict(r) for r in rows]
        if rows:
            table.update(_rows_to_arrow_ipc(rows, schema, index, date_keys))

    def update_positions(self, rows: Iterable[dict]) -> None:
        self._push(self.positions, rows, POSITIONS_SCHEMA, "symbol")

    def update_equity(self, rows: Iterable[dict]) -> None:
        self._push(self.equity, rows, EQUITY_SCHEMA, "date", date_keys=("date",))

    def update_fills(self, rows: Iterable[dict]) -> None:
        self._push(self.fills, rows, FILLS_SCHEMA, None)

    def set_meta(self, **values: object) -> None:
        """Upsert ``key=value`` pairs into the ``meta`` table (values are
        stored as strings; None clears a key's value).  Keys the page reads:
        ``data_source`` (``"demo"`` shows the DEMO DATA banner) and
        ``note`` (shown next to the title / in the banner)."""
        rows = [{"key": k, "value": None if v is None else str(v)} for k, v in values.items()]
        self._push(self.meta, rows, META_SCHEMA, "key")

    def get_meta(self) -> dict[str, str | None]:
        view = self.meta.view()
        try:
            return {r["key"]: r["value"] for r in view.to_records()}
        finally:
            view.delete()

    def table_sizes(self) -> dict[str, int]:
        """Rows actually held by each data table (what a viewer will see)."""
        return {
            "positions": self.positions.size(),
            "equity": self.equity.size(),
            "fills": self.fills.size(),
        }


# --------------------------------------------------------------------------
# Tornado wiring
# --------------------------------------------------------------------------


def _is_loopback(host: str) -> bool:
    host = host.strip("[]").lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def normalise_origin(origin: str) -> str:
    """``'HTTP://LocalHost:3000/'`` -> ``'http://localhost:3000'``.

    Raises ``ValueError`` unless ``origin`` is ``scheme://host[:port]`` (no
    path, query or credentials) -- what a browser puts in ``Origin``."""
    text = origin.strip().rstrip("/")
    parts = urlsplit(text)
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.path
        or parts.query
        or parts.fragment
        or "@" in parts.netloc
    ):
        raise ValueError(
            f"not an origin: {origin!r} (expected scheme://host[:port], "
            "e.g. http://localhost:3000)"
        )
    return f"{parts.scheme}://{parts.netloc.lower()}"


def origin_allowed(
    origin: str,
    host_header: str | None,
    allowed_origins: Iterable[str] = (),
    bind_host: str = "127.0.0.1",
) -> bool:
    """The websocket origin policy (see the module's security section).

    ``True`` iff ``origin`` is in ``allowed_origins`` (already normalised
    with :func:`normalise_origin`), or it is same-origin -- its ``host:port``
    equals the ``Host`` header -- and, when ``bind_host`` is a loopback
    address, names a loopback host or ``bind_host`` itself (DNS-rebinding
    guard).  Requests without an ``Origin`` header never reach this: Tornado
    accepts them (non-browser clients).
    """
    try:
        normalised = normalise_origin(origin)
    except ValueError:  # "null" (file://, sandboxed iframe), garbage, ...
        return False
    if normalised in set(allowed_origins):
        return True
    netloc = urlsplit(normalised).netloc
    if not host_header or netloc != host_header.strip().lower():
        return False
    if _is_loopback(bind_host):
        hostname = (urlsplit(normalised).hostname or "").lower()
        return hostname in LOOPBACK_HOSTNAMES or hostname == bind_host.strip("[]").lower()
    return True


_CONNECTIONS_SETTING = "quantstack_ws_connections"


class OriginCheckedPerspectiveHandler(PerspectiveTornadoHandler):
    """``PerspectiveTornadoHandler`` with a real ``check_origin``.

    The upstream handler's ``check_origin`` returns ``True`` for everything,
    so any web page open in the user's browser could open
    ``ws://127.0.0.1:PORT/ws`` and read or ``clear()`` the tables.  This
    subclass applies :func:`origin_allowed` (same-origin, plus an explicit
    allow-list) and rejects everything else with 403.  It also tracks open
    connections so :class:`BackgroundDashboard` can close them on ``stop()``.
    """

    def initialize(  # type: ignore[override]
        self,
        perspective_server=perspective.GLOBAL_SERVER,
        allowed_origins: Iterable[str] = (),
        bind_host: str = "127.0.0.1",
        **kwargs,
    ) -> None:
        super().initialize(perspective_server=perspective_server, **kwargs)
        self.allowed_origins = frozenset(allowed_origins)
        self.bind_host = bind_host

    def check_origin(self, origin: str) -> bool:
        host = self.request.headers.get("Host")
        ok = origin_allowed(origin, host, self.allowed_origins, self.bind_host)
        if not ok:
            log.warning(
                "rejected websocket from Origin %r (Host %r): not same-origin "
                "and not in --allow-origin", origin, host,
            )
        return ok

    def open(self) -> None:
        super().open()
        self.application.settings[_CONNECTIONS_SETTING].add(self)

    def on_close(self) -> None:
        self.application.settings[_CONNECTIONS_SETTING].discard(self)
        super().on_close()


_CDN_PREFIX = "https://cdn.jsdelivr.net/npm/"
_LOCAL_NPM_PREFIX = "/npm/"
_CDN_PIN_RE = re.compile(
    r"https://cdn\.jsdelivr\.net/npm/(@perspective-dev/[A-Za-z0-9._-]+)@([^/\"'\s]+)/"
)


def npm_pins_in_index_html(path: Path | str | None = None) -> dict[str, list[str]]:
    """``{"@perspective-dev/<pkg>": [versions...]}`` for every jsdelivr URL
    in ``static/index.html`` (script tags, the module ``import`` and the
    stylesheet link).  One version per package is the healthy state."""
    html = Path(path if path is not None else INDEX_HTML).read_text()
    pins: dict[str, set[str]] = {}
    for package, version in _CDN_PIN_RE.findall(html):
        pins.setdefault(package, set()).add(version)
    return {k: sorted(v) for k, v in sorted(pins.items())}


class _LocalAssetsIndexHandler(tornado.web.RequestHandler):
    """``index.html`` with the jsdelivr prefix pointed at ``/npm/`` (only
    registered when ``npm_dir`` is given)."""

    def get(self) -> None:
        html = INDEX_HTML.read_text().replace(
            _CDN_PREFIX + "@perspective-dev/", _LOCAL_NPM_PREFIX + "@perspective-dev/"
        )
        self.set_header("Content-Type", "text/html; charset=utf-8")
        self.set_header("Cache-Control", "no-cache")
        self.write(html)


class _NpmAssetHandler(tornado.web.StaticFileHandler):
    _TYPES = {".wasm": "application/wasm", ".js": "text/javascript", ".mjs": "text/javascript"}

    def get_content_type(self) -> str:
        assert self.absolute_path is not None
        return self._TYPES.get(Path(self.absolute_path).suffix) or super().get_content_type()


def _npm_asset_routes(npm_dir: Path | str) -> list:
    """Routes serving the page's pinned ``@perspective-dev/*`` packages from
    ``npm_dir/<name>/package/`` (unpacked npm tarballs), each checked
    against the version the page pins."""
    npm_dir = Path(npm_dir)
    routes = []
    for package, versions in npm_pins_in_index_html().items():
        short = package.split("/", 1)[1]
        root = npm_dir / short / "package"
        manifest = root / "package.json"
        if not manifest.is_file():
            raise FileNotFoundError(
                f"npm_dir {npm_dir}: {manifest} is missing -- unpack the npm "
                f"tarball of {package}@{versions[0]} as {npm_dir / short}/package/"
            )
        meta = json.loads(manifest.read_text())
        for version in versions:
            if meta.get("name") != package or meta.get("version") != version:
                raise ValueError(
                    f"{manifest} is {meta.get('name')}@{meta.get('version')}, but "
                    f"index.html pins {package}@{version}"
                )
            prefix = re.escape(f"{_LOCAL_NPM_PREFIX}{package}@{version}/")
            routes.append((prefix + r"(.*)", _NpmAssetHandler, {"path": str(root)}))
    return routes


def make_app(
    server: "perspective.Server",
    websocket_max_message_size: int = DEFAULT_WEBSOCKET_MAX_MESSAGE_SIZE,
    *,
    allowed_origins: Iterable[str] = (),
    bind_host: str = "127.0.0.1",
    npm_dir: Path | str | None = None,
) -> tornado.web.Application:
    """Build the Tornado app: the websocket route ``/ws`` and the page.

    * ``/ws`` is :class:`OriginCheckedPerspectiveHandler`: no auth, but
      browsers must be same-origin (or listed in ``allowed_origins``, full
      ``scheme://host[:port]`` strings); see the module's security section.
      ``bind_host`` is the address the app will be bound to -- it switches
      the DNS-rebinding guard on for loopback binds, so pass the real one
      when binding elsewhere (:func:`serve` and :class:`BackgroundDashboard`
      do).
    * ``/`` serves ``static/index.html``; with ``npm_dir`` the page's
      jsdelivr URLs are rewritten to ``/npm/...`` and served from the
      unpacked npm tarballs there (offline use; versions are checked).
    """
    allowed = frozenset(normalise_origin(o) for o in allowed_origins)
    routes: list = [
        (
            r"/ws",
            OriginCheckedPerspectiveHandler,
            {"perspective_server": server, "allowed_origins": allowed, "bind_host": bind_host},
        ),
    ]
    if npm_dir is not None:
        routes += _npm_asset_routes(npm_dir)
        routes.append((r"/(?:index\.html)?", _LocalAssetsIndexHandler))
    routes.append(
        (
            r"/(.*)",
            tornado.web.StaticFileHandler,
            {"path": str(STATIC_DIR), "default_filename": "index.html"},
        )
    )
    return tornado.web.Application(
        routes,
        websocket_max_message_size=websocket_max_message_size,
        **{_CONNECTIONS_SETTING: set()},
    )


def _warn_if_exposed(host: str) -> None:
    if not _is_loopback(host):
        print(
            f"[dashboard] WARNING: bound to {host} -- the websocket has NO "
            "authentication (browsers are limited to same-origin, other "
            "clients are not). Anyone who can reach this host:port can read "
            "and write every table.",
            file=sys.stderr,
        )


def serve(
    sink: PerspectiveSink,
    port: int,
    host: str = "127.0.0.1",
    *,
    allowed_origins: Iterable[str] = (),
    npm_dir: Path | str | None = None,
) -> None:
    """Serve ``sink``'s tables forever. Blocks; run this as your process's
    main loop (the CLI below is a thin wrapper around it).  For a
    non-blocking server use :class:`BackgroundDashboard`.

    SECURITY: binds to ``host`` verbatim with no auth in front of it -- see
    the module docstring. Only pass ``host="0.0.0.0"`` (or another
    non-loopback address) when you mean to expose this to your network.
    """
    app = make_app(sink.server, allowed_origins=allowed_origins, bind_host=host, npm_dir=npm_dir)
    app.listen(port, address=host)
    print(f"[dashboard] serving on http://{_url_host(host)}:{port}/  (websocket: /ws)")
    _warn_if_exposed(host)
    tornado.ioloop.IOLoop.current().start()


def _url_host(host: str) -> str:
    """A host a client can put in a URL for a server bound to ``host``."""
    if host in ("", "0.0.0.0"):
        return "127.0.0.1"
    if host == "::":
        return "[::1]"
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


class BackgroundDashboard:
    """Serve a sink without blocking: Tornado runs in a daemon thread on its
    own asyncio event loop.

    >>> dash = BackgroundDashboard(sink, port=0).start()   # returns once listening
    >>> dash.url            # 'http://127.0.0.1:54321/'
    >>> dash.stop()         # closes websockets, stops the loop, joins the thread

    Also a context manager (``with BackgroundDashboard(sink).start() as d:``;
    ``__enter__`` starts it if needed).  ``port=0`` lets the OS pick a free
    port (read it back from ``.port``).  The listening socket is bound in
    the calling thread, so a busy port raises ``OSError`` from
    :meth:`start` itself.  The sink may be pushed to from any thread while
    serving (Perspective's server is thread-safe; the tests do exactly
    this).  Same security posture as :func:`serve`.
    """

    def __init__(
        self,
        sink: "PerspectiveSink | perspective.Server",
        host: str = "127.0.0.1",
        port: int = 0,
        *,
        allowed_origins: Iterable[str] = (),
        npm_dir: Path | str | None = None,
        websocket_max_message_size: int = DEFAULT_WEBSOCKET_MAX_MESSAGE_SIZE,
    ) -> None:
        self.sink = sink
        self.server = getattr(sink, "server", sink)
        self.host = host
        self.requested_port = port
        self.port: int | None = None
        self.app = make_app(
            self.server,
            websocket_max_message_size,
            allowed_origins=allowed_origins,
            bind_host=host,
            npm_dir=npm_dir,
        )
        self._thread: threading.Thread | None = None
        self._io_loop: tornado.ioloop.IOLoop | None = None
        self._http_server: tornado.httpserver.HTTPServer | None = None
        self._ready = threading.Event()
        self._error: BaseException | None = None

    # -- addresses ---------------------------------------------------------
    @property
    def url(self) -> str:
        return f"http://{_url_host(self.host)}:{self.port}/"

    @property
    def ws_url(self) -> str:
        return f"ws://{_url_host(self.host)}:{self.port}/ws"

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # -- lifecycle ---------------------------------------------------------
    def start(self, timeout: float = 10.0) -> "BackgroundDashboard":
        if self._thread is not None:
            raise RuntimeError("BackgroundDashboard.start() called twice")
        sockets = tornado.netutil.bind_sockets(self.requested_port, address=self.host)
        self.port = sockets[0].getsockname()[1]
        self._thread = threading.Thread(
            target=self._run, args=(sockets,), name=f"quantstack-dashboard:{self.port}",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout=timeout):
            self.stop(timeout=timeout)
            raise RuntimeError(f"dashboard server did not start within {timeout}s")
        if self._error is not None:
            raise RuntimeError("dashboard server thread failed to start") from self._error
        _warn_if_exposed(self.host)
        return self

    def _run(self, sockets) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        io_loop = None
        try:
            io_loop = tornado.ioloop.IOLoop.current()
            http_server = tornado.httpserver.HTTPServer(self.app)
            http_server.add_sockets(sockets)
            self._io_loop, self._http_server = io_loop, http_server
            io_loop.add_callback(self._ready.set)
            io_loop.start()
        except BaseException as exc:  # noqa: BLE001 -- reported via start()
            self._error = exc
            for s in sockets:
                s.close()
            self._ready.set()
        finally:
            # Let cancelled tasks unwind, then close the loop and every fd
            # still registered on it (e.g. a websocket that ignored close).
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            if io_loop is not None:
                io_loop.close(all_fds=True)
            else:
                loop.close()

    async def _shutdown(self, grace: float) -> None:
        assert self._http_server is not None
        self._http_server.stop()  # stop accepting
        connections = self.app.settings[_CONNECTIONS_SETTING]
        for handler in list(connections):
            handler.close(1001, "dashboard stopping")
        deadline = time.monotonic() + grace
        while connections and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        try:
            await asyncio.wait_for(self._http_server.close_all_connections(), grace)
        except asyncio.TimeoutError:
            pass
        tornado.ioloop.IOLoop.current().stop()

    def stop(self, timeout: float = 10.0) -> None:
        """Close open websockets (code 1001), stop listening, stop the loop
        and join the thread.  Idempotent."""
        thread = self._thread
        if thread is None or not thread.is_alive():
            return
        if self._io_loop is not None:
            self._io_loop.add_callback(self._shutdown, min(2.0, timeout / 2))
        thread.join(timeout=timeout)
        if thread.is_alive():
            raise RuntimeError(f"dashboard server thread did not stop within {timeout}s")

    def __enter__(self) -> "BackgroundDashboard":
        return self if self._thread is not None else self.start()

    def __exit__(self, *exc_info) -> None:
        self.stop()


def serve_in_background(
    sink: "PerspectiveSink | perspective.Server",
    host: str = "127.0.0.1",
    port: int = 0,
    **kwargs,
) -> BackgroundDashboard:
    """``BackgroundDashboard(sink, host, port, **kwargs).start()``: returns a
    running handle with ``.url``, ``.ws_url``, ``.port`` and ``.stop()``."""
    return BackgroundDashboard(sink, host, port, **kwargs).start()


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


def _rel(path: Path | str | None) -> str | None:
    """Repo-relative POSIX path for the summary; absolute only for files
    outside the repository (e.g. a temp dir), which have no relative form."""
    if path is None:
        return None
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def _scrub(text: str | None) -> str | None:
    """Strip the repo root from messages (exception texts embed paths)."""
    if text is None:
        return None
    return text.replace(str(REPO_ROOT) + os.sep, "")


def _demo_dataset() -> tuple[list[dict], list[dict], list[dict]]:
    """A tiny, self-contained dataset so the page shows *something* useful
    when the execution module hasn't written its CSVs yet.  The page shows a
    DEMO DATA banner whenever this is what is being served."""
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
    for d, step in zip(dates, rng_steps, strict=True):
        equity += step
        equity_rows.append({"date": d.date().isoformat(), "equity": equity})
    fills_rows = [
        {"ts": f"{dates[0].date().isoformat()}T14:30:00", "symbol": "AAPL", "side": "BUY", "qty": 120.0, "price": 187.5},
        {"ts": f"{dates[1].date().isoformat()}T14:31:00", "symbol": "MSFT", "side": "BUY", "qty": 45.0, "price": 409.0},
        {"ts": f"{dates[2].date().isoformat()}T14:32:00", "symbol": "GOOG", "side": "SELL", "qty": 30.0, "price": 170.0},
    ]
    return positions_rows, equity_rows, fills_rows


_POSITIONS_REQUIRED = ("symbol", "qty", "last")


def _load_positions_csv(path: Path) -> list[dict]:
    """POSITIONS_SCHEMA rows via ``contracts.read_positions_csv`` -- the one
    place the stack knows how the execution module writes this file.

    A file with the positions header but no rows is a legitimately *flat
    book* (everything sold) and returns ``[]``; ``read_positions_csv``
    raises on it, which used to throw the dashboard back to demo data.  A
    0-byte file (writer still mid-write) or missing columns still raise."""
    df = pd.read_csv(path)
    missing = [c for c in _POSITIONS_REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing positions column(s) {missing}")
    if df.empty:
        return []
    return read_positions_csv(path).to_rows()


def _load_equity_csv(path: Path, column: str | None = None) -> tuple[list[dict], str]:
    """One curve of an equity CSV as EQUITY_SCHEMA rows, plus the source
    column name.

    Delegates to ``contracts.read_equity_csv`` (the reader paired with
    ``contracts.write_equity_csv``): a ``date`` column and one or more
    ``equity*`` columns.  ``column=None`` takes the plain ``equity`` column
    if there is one, else the *first* ``equity*`` column -- the strategy's
    own curve by convention (the execution module writes ``equity_hrp``
    before the ``equity_equal_*`` benchmarks).  The column actually used is
    returned so the CLI can print it and record it in the summary
    (``equity_source_column``); ``contracts.equity_csv_columns`` lists the
    alternatives.  A blank cell becomes NaN here and null in the table (it
    is *not* dropped).  Raises ``ValueError`` for a file without ``date`` or
    ``equity*`` columns or an unknown ``column``.
    """
    series = read_equity_csv(path, column)
    rows = [
        {"date": ts.strftime("%Y-%m-%d"), "equity": float(value)}
        for ts, value in series.items()
    ]
    return rows, str(series.name)


def _load_fills_csv(path: Path) -> list[dict]:
    """FILLS_SCHEMA rows from a fills CSV, validated by the same coercion the
    sink applies: ``ValueError`` if a schema column is missing or a value
    cannot be coerced (e.g. ``qty = "ten"``).  Extra columns are ignored."""
    df = pd.read_csv(path)
    missing = [c for c in FILLS_SCHEMA if c not in df.columns]
    if missing:
        raise ValueError(f"missing fills column(s) {missing} (have {list(df.columns)})")
    rows = df[list(FILLS_SCHEMA)].to_dict(orient="records")
    if rows:
        _rows_to_arrow_ipc(rows, FILLS_SCHEMA, None)  # validate; raises on bad values
    return rows


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
    fills_warning: str | None = None  # why fills were skipped, if they were
    equity_columns_available: list[str] = field(default_factory=list)
    equity_csv: Path | None = None
    positions_csv: Path | None = None

    @property
    def positions_flat(self) -> bool:
        """A real (non-demo) positions file with no rows: a flat book."""
        return not self.is_demo and not self.positions_rows

    def meta(self) -> dict[str, str]:
        """What :func:`populate_sink` puts in the ``meta`` table."""
        if self.is_demo:
            return {
                "data_source": "demo",
                "note": f"Reason: {_scrub(self.fallback_reason)}",
            }
        note = f"replay of {_rel(self.equity_csv)} [{self.equity_col}]"
        if self.positions_flat:
            note += "; flat book (no open positions)"
        if self.fills_warning:
            note += "; fills skipped (see dashboard summary)"
        return {"data_source": "replay", "note": note}


def demo_replay(reason: str, equity_csv: Path | None = None, positions_csv: Path | None = None) -> ReplayData:
    """The synthetic demo dataset as a :class:`ReplayData` (``is_demo``)."""
    positions_rows, equity_rows, fills_rows = _demo_dataset()
    return ReplayData(
        positions_rows, equity_rows, fills_rows, True, None, None, reason,
        equity_csv=equity_csv, positions_csv=positions_csv,
    )


def load_replay(
    equity_csv: Path,
    positions_csv: Path,
    fills_csv: Path | None,
    equity_column: str | None = None,
) -> ReplayData:
    """Replay real execution-module output; degrade instead of crashing.

    * Equity or positions missing or unparseable -> the synthetic demo
      dataset (and its own fills), with ``fallback_reason`` saying why.  A
      header-only positions file is *not* a failure: it is a flat book and is
      served as an empty positions table next to the real equity curve.
    * Fills unparseable (missing column, non-numeric qty, ...) -> no fills,
      with ``fills_warning`` saying why; equity/positions are still served.
    * ``fills_csv`` is loaded only if given *and* present; it is never
      silently swapped for another run's file (a custom ``--replay`` used to
      pick up the repo's default fills, mixing sources on one screen).
    """
    equity_csv, positions_csv = Path(equity_csv), Path(positions_csv)
    missing = [_rel(p) for p in (equity_csv, positions_csv) if not p.exists()]
    if missing:
        reason = "not found: " + ", ".join(missing)
    else:
        try:
            positions_rows = _load_positions_csv(positions_csv)
            equity_rows, equity_col = _load_equity_csv(equity_csv, equity_column)
            equity_columns = equity_csv_columns(equity_csv)
        except Exception as exc:  # noqa: BLE001 -- deliberately broad: any
            # parse failure here should degrade to the demo, not crash the
            # dashboard, since the writer (another module) may still be
            # mid-write or using a slightly different column layout.
            reason = f"could not parse ({exc!r})"
        else:
            fills_path = (
                Path(fills_csv)
                if fills_csv is not None and Path(fills_csv).exists()
                else None
            )
            fills_rows: list[dict] = []
            fills_warning = None
            if fills_path is not None:
                try:
                    fills_rows = _load_fills_csv(fills_path)
                except Exception as exc:  # noqa: BLE001 -- same guard, fills only
                    fills_warning = f"skipped fills from {_rel(fills_path)}: {exc!r}"
            return ReplayData(
                positions_rows, equity_rows, fills_rows, False, equity_col,
                fills_path if fills_warning is None else None, None,
                fills_warning=fills_warning,
                equity_columns_available=equity_columns,
                equity_csv=equity_csv,
                positions_csv=positions_csv,
            )
    return demo_replay(reason, equity_csv, positions_csv)


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


def populate_sink(sink: PerspectiveSink, data: ReplayData) -> None:
    """Push a :class:`ReplayData` into ``sink`` and label it in ``meta``."""
    sink.update_positions(data.positions_rows)
    sink.update_equity(data.equity_rows)
    sink.update_fills(data.fills_rows)
    sink.set_meta(**data.meta())


# --------------------------------------------------------------------------
# In-process websocket smoke test (the wire this module exists to prove)
# --------------------------------------------------------------------------

# Deliberately not a "round" number: the list-of-dicts JSON path used to
# return this 1 ulp off (...51); the Arrow path must return it bit-exact.
_SELFTEST_FLOAT = 98.27639451941653
_SELFTEST_FOREIGN_ORIGIN = "https://evil.example.com"


async def _read_tables(ws_url: str, table_names: Iterable[str], headers: Mapping[str, str] | None = None) -> dict:
    """Connect ``perspective.AsyncClient`` over a real websocket and read
    each table back with ``view().to_records()``.  Responses are fed to the
    client on *this* (the client's) event loop, as perspective's reference
    test does; strong refs keep the tasks from being GC'd mid-flight."""
    loop = asyncio.get_running_loop()
    client_holder: dict = {}
    pending: set = set()

    def on_message(msg):
        if msg is None:  # connection closed
            return
        task = loop.create_task(client_holder["client"].handle_response(msg))
        pending.add(task)
        task.add_done_callback(pending.discard)

    request = tornado.httpclient.HTTPRequest(ws_url, headers=dict(headers or {}))
    conn = await tornado.websocket.websocket_connect(request, on_message_callback=on_message)

    async def handle_request(msg: bytes) -> None:
        conn.write_message(msg, binary=True)

    client = perspective.AsyncClient(handle_request)
    client_holder["client"] = client
    try:
        out = {"hosted_tables": sorted(await client.get_hosted_table_names())}
        for name in table_names:
            table = await client.open_table(name)
            view = await table.view()
            out[name] = await view.to_records()
            await view.delete()
        return out
    finally:
        conn.close()


class _DropAll(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return False


async def _handshake_status(ws_url: str, headers: Mapping[str, str]) -> int:
    """101 if the websocket upgrade is accepted, else the HTTP status."""
    request = tornado.httpclient.HTTPRequest(ws_url, headers=dict(headers))
    try:
        conn = await tornado.websocket.websocket_connect(request)
    except tornado.httpclient.HTTPClientError as exc:
        return exc.code
    conn.close()
    return 101


def run_wire_selftest(host: str = "127.0.0.1", timeout: float = 10.0) -> dict:
    """Start a *real* Tornado+Perspective server on an OS-assigned free port
    (:class:`BackgroundDashboard`: a background thread with its own asyncio
    loop), push rows through :class:`PerspectiveSink`, then connect an actual
    websocket client (``tornado.websocket.websocket_connect`` +
    ``perspective.AsyncClient``) from this thread's asyncio loop and read
    them back over the wire.  Also checks the origin policy: a handshake
    with a foreign ``Origin`` must get 403, a same-origin one 101.

    This is the same mechanism ``tests/test_dashboard.py`` exercises; it's
    factored out here so the CLI can run it once at startup (proof the wire
    is live) and record its result in ``results/dashboard_summary.json``.
    Returns a dict of the numbers that go in that file.
    """
    sink = PerspectiveSink()

    # Push once, then push an update to the *same* symbol -- this is what
    # proves the indexed table overwrites in place rather than appending.
    sink.update_positions([{"symbol": "AAPL", "qty": 10.0, "last": 100.0, "value": 1000.0}])
    sink.update_positions([{"symbol": "AAPL", "qty": 25.0, "last": 101.5, "value": 2537.5}])
    sink.update_positions([{"symbol": "MSFT", "qty": 5.0, "last": _SELFTEST_FLOAT, "value": 5.0 * _SELFTEST_FLOAT}])
    sink.update_equity([{"date": "2026-09-24", "equity": 1_000_000.0}])
    sink.update_equity([{"date": "2026-09-25", "equity": 1_004_000.0}])
    sink.update_fills([{"ts": "2026-09-25T14:30:00", "symbol": "AAPL", "side": "BUY", "qty": 25.0, "price": 101.5}])

    async def client_check(dash: BackgroundDashboard) -> dict:
        out = await _read_tables(dash.ws_url, TABLE_NAMES)
        same_origin = dash.url.rstrip("/")
        # The rejection is the expected outcome here: keep its warning and
        # the 403 access-log line out of the CLI output.
        quiet = [logging.getLogger("quantstack.dashboard"), logging.getLogger("tornado.access")]
        drop = _DropAll()
        for logger in quiet:
            logger.addFilter(drop)
        try:
            out["foreign_origin_status"] = await _handshake_status(
                dash.ws_url, {"Origin": _SELFTEST_FOREIGN_ORIGIN}
            )
            await asyncio.sleep(0.05)  # the access log is written after the reply
        finally:
            for logger in quiet:
                logger.removeFilter(drop)
        out["same_origin_status"] = await _handshake_status(dash.ws_url, {"Origin": same_origin})
        return out

    with BackgroundDashboard(sink, host=host, port=0).start(timeout=timeout) as dash:
        port = dash.port
        result = asyncio.run(asyncio.wait_for(client_check(dash), timeout=timeout))

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
        "foreign_origin": _SELFTEST_FOREIGN_ORIGIN,
        "foreign_origin_status": result["foreign_origin_status"],
        "same_origin_status": result["same_origin_status"],
        "origin_policy_ok": (
            result["foreign_origin_status"] == 403 and result["same_origin_status"] == 101
        ),
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _previous_wire_selftest(paths: Iterable[Path]) -> tuple[dict, Path] | None:
    """The first measured ``wire_selftest`` block found in ``paths``."""
    for path in paths:
        try:
            block = json.loads(Path(path).read_text()).get("wire_selftest")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(block, dict) and block.get("port_used") is not None:
            return block, Path(path)
    return None


def _npm_block() -> dict:
    """The ``@perspective-dev/*`` pins actually present in index.html."""
    pins = npm_pins_in_index_html()
    block: dict = {
        name: versions[0] if len(versions) == 1 else versions
        for name, versions in pins.items()
    }
    block["source_file"] = _rel(INDEX_HTML)
    block["all_pinned_to_perspective_python"] = bool(pins) and all(
        versions == [perspective.__version__] for versions in pins.values()
    )
    block["note"] = (
        "read from the page's jsdelivr URLs; renamed from @finos/perspective* "
        "upstream -- see the module docstring in quantstack/dashboard/server.py"
    )
    return block


def _write_summary(
    selftest: dict | None,
    replay_info: dict,
    out_path: Path | None = None,
    previous_from: Iterable[Path] = (),
    extra: Mapping | None = None,
) -> Path:
    """Write the dashboard summary JSON to ``out_path`` (default: the
    canonical ``RESULTS_DIR/dashboard_summary.json``).

    ``selftest=None`` means ``--no-selftest``: the websocket evidence from
    the last run that *did* measure it (first hit in ``out_path`` then
    ``previous_from``) is carried over, flagged ``measured_this_run: false``,
    instead of being overwritten with nulls.
    """
    out_path = Path(out_path) if out_path is not None else RESULTS_DIR / SUMMARY_NAME
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if selftest is None:
        found = _previous_wire_selftest([out_path, *previous_from])
        if found is not None:
            wire = dict(found[0])
            wire["measured_this_run"] = False
            wire["note"] = (
                f"carried over unchanged from {_rel(found[1])}; this run used "
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
            "foreign_origin_handshake": {
                "origin": selftest.get("foreign_origin"),
                "http_status": selftest.get("foreign_origin_status"),
            },
            "same_origin_handshake_http_status": selftest.get("same_origin_status"),
            "origin_policy_enforced": selftest.get("origin_policy_ok"),
        }
    summary = {
        "perspective_version": perspective.__version__,
        "tables": {
            "positions": {"schema": POSITIONS_SCHEMA, "index": "symbol"},
            "equity": {"schema": EQUITY_SCHEMA, "index": "date"},
            "fills": {"schema": FILLS_SCHEMA, "index": None},
            "meta": {"schema": META_SCHEMA, "index": "key"},
        },
        "update_path": "Arrow IPC bytes (typed from contracts schemas), not list-of-dicts JSON",
        "row_semantics": (
            "whole-row: every schema column is sent for every row, so a key "
            "missing from a row nulls that cell; equity date keys are "
            "normalised to YYYY-MM-DD"
        ),
        "security": {
            "authentication": "none",
            "websocket_origin_policy": (
                "same-origin only (Origin host:port must equal Host; loopback "
                "hosts only when bound to loopback) plus explicit "
                "--allow-origin entries; clients sending no Origin header "
                "(non-browser) are accepted"
            ),
            "default_bind_host": "127.0.0.1",
        },
        "npm_packages_used_by_static_index_html": _npm_block(),
        "wire_selftest": wire,
        "replay": replay_info,
    }
    if extra:
        summary.update(extra)
    out_path.write_text(json.dumps(summary, indent=2, default=str) + "\n")
    return out_path


def _size_warnings(loaded: dict[str, int], served: dict[str, int]) -> list[str]:
    return [
        f"{name}: {loaded[name]} row(s) loaded but table holds {served[name]} "
        "(duplicate index keys collapse by design; any other gap is lost data)"
        for name in TABLE_NAMES
        if loaded[name] != served[name]
    ]


def _same_file(a: Path | str, b: Path | str) -> bool:
    return Path(a).resolve() == Path(b).resolve()


def _summary_destination(
    args: argparse.Namespace, equity_csv: Path, canonical: bool
) -> tuple[Path, str]:
    """Where this run's summary goes, and why.

    ``--summary`` wins; a canonical run (default inputs, self-test measured)
    writes ``RESULTS_DIR/dashboard_summary.json``; any other run writes
    ``dashboard_summary.json`` next to the replayed equity CSV -- unless that
    *is* the canonical file (e.g. ``--no-selftest`` on the default inputs)
    or the directory does not exist, in which case it writes
    ``RESULTS_DIR/dashboard_summary.adhoc.json``.  So ad-hoc runs never
    overwrite the canonical summary.
    """
    if args.summary is not None:
        return Path(args.summary), "--summary"
    canonical_path = RESULTS_DIR / SUMMARY_NAME
    if canonical:
        return canonical_path, "canonical run (default inputs, self-test measured)"
    candidate = equity_csv.parent / SUMMARY_NAME
    protected = (canonical_path, DEFAULT_EQUITY_CSV.parent / SUMMARY_NAME)
    if not equity_csv.parent.is_dir() or any(_same_file(candidate, p) for p in protected):
        return RESULTS_DIR / ADHOC_SUMMARY_NAME, "ad-hoc run"
    return candidate, "ad-hoc run (next to the replayed files)"


def _origin_arg(value: str) -> str:
    try:
        return normalise_origin(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m quantstack.dashboard.server",
        description=(
            "Serve the quantstack dashboard (Perspective + Tornado). "
            "SECURITY: the websocket handler has NO authentication; browsers "
            "are limited to same-origin pages. Binds to 127.0.0.1 by default; "
            "pass --host 0.0.0.0 to expose it on your network (only do this "
            "on a trusted network)."
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
        "--allow-origin",
        action="append",
        default=[],
        type=_origin_arg,
        metavar="ORIGIN",
        help=(
            "extra browser origin (scheme://host[:port]) allowed to open the "
            "websocket besides the page's own origin; repeatable. Default: "
            "same-origin only."
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
            f"(default: {_rel(DEFAULT_EQUITY_CSV)} {_rel(DEFAULT_POSITIONS_CSV)}). "
            "If either file is missing or unparseable, a small synthetic demo "
            "dataset is served instead (the page shows a DEMO DATA banner)."
        ),
    )
    parser.add_argument(
        "--equity-column",
        default=None,
        metavar="COLUMN",
        help=(
            "which equity* column of EQUITY_CSV to plot (default: 'equity' if "
            "present, else the first equity* column)"
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
            "The previous self-test result is carried into the summary."
        ),
    )
    parser.add_argument(
        "--once",
        "--no-serve",
        dest="once",
        action="store_true",
        help=(
            "replay + self-test + write the summary, then exit 0 without "
            "serving (what `make all` uses)"
        ),
    )
    parser.add_argument(
        "--summary",
        metavar="PATH",
        default=None,
        help=(
            f"where to write the summary JSON. Default: {_rel(RESULTS_DIR / SUMMARY_NAME)} "
            "for a canonical run (default inputs, self-test on); otherwise "
            f"{SUMMARY_NAME} next to EQUITY_CSV (or {ADHOC_SUMMARY_NAME} in "
            "results/), so ad-hoc runs never overwrite the canonical file"
        ),
    )
    parser.add_argument(
        "--npm-dir",
        metavar="DIR",
        default=None,
        help=(
            "serve the page's pinned @perspective-dev/* JS from unpacked npm "
            "tarballs in DIR (DIR/client/package/..., DIR/viewer/package/..., "
            "...) instead of cdn.jsdelivr.net, for offline use"
        ),
    )
    args = parser.parse_args(argv)

    # Fail fast, before the self-test and before touching the summary JSON.
    if not args.once:
        bind_error = _port_unavailable(args.host, args.port)
        if bind_error is not None:
            print(
                f"[dashboard] cannot bind {args.host}:{args.port}: {bind_error} "
                "-- pick another --port",
                file=sys.stderr,
            )
            raise SystemExit(2)
    if args.npm_dir is not None:
        try:  # validate now rather than after the self-test
            _npm_asset_routes(args.npm_dir)
        except (OSError, ValueError) as exc:
            print(f"[dashboard] --npm-dir: {exc}", file=sys.stderr)
            raise SystemExit(2) from None

    equity_csv, positions_csv = Path(args.replay[0]), Path(args.replay[1])
    if args.fills is not None:
        fills_csv = Path(args.fills)
        if not fills_csv.exists():
            print(f"[dashboard] --fills {fills_csv} not found; no fills will be loaded")
    else:
        fills_csv = equity_csv.parent / FILLS_CSV_NAME

    default_inputs = (
        _same_file(equity_csv, DEFAULT_EQUITY_CSV)
        and _same_file(positions_csv, DEFAULT_POSITIONS_CSV)
        and _same_file(fills_csv, DEFAULT_FILLS_CSV)
        and args.equity_column is None
    )
    canonical = default_inputs and not args.no_selftest

    data = load_replay(equity_csv, positions_csv, fills_csv, args.equity_column)
    if data.is_demo:
        print(
            f"[dashboard] replay unavailable ({data.fallback_reason}) -- the "
            "execution module may still be building; serving synthetic demo "
            "data instead (the page shows a DEMO DATA banner)"
        )
    else:
        print(
            f"[dashboard] replaying {_rel(positions_csv)} and {_rel(equity_csv)} "
            f"(equity column: {data.equity_col!r}; fills: "
            f"{_rel(data.fills_csv) if data.fills_csv else 'none'})"
        )
        if data.positions_flat:
            print("[dashboard] positions file has no rows: serving a flat book")
        if data.fills_warning:
            print(f"[dashboard] WARNING: {data.fills_warning}", file=sys.stderr)

    sink = PerspectiveSink(server=perspective.Server())
    populate_sink(sink, data)
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
            f"float bit-exact ok={selftest['float_bit_exact_ok']}, "
            f"foreign origin -> {selftest['foreign_origin_status']}, "
            f"same origin -> {selftest['same_origin_status']}"
        )

    summary_path, why = _summary_destination(args, equity_csv, canonical)
    summary_path = _write_summary(
        selftest,
        replay_info={
            "is_demo": data.is_demo,
            "fallback_reason": _scrub(data.fallback_reason),
            "equity_csv": _rel(equity_csv),
            "positions_csv": _rel(positions_csv),
            "fills_csv": _rel(data.fills_csv),
            "fills_warning": _scrub(data.fills_warning),
            "equity_source_column": data.equity_col,
            "equity_columns_available": data.equity_columns_available,
            "positions_flat_book": data.positions_flat,
            # rows read from the CSVs (or the demo) ...
            "n_positions": loaded["positions"],
            "n_equity_points": loaded["equity"],
            "n_fills": loaded["fills"],
            # ... and rows the served tables actually hold
            "table_sizes_after_load": served,
            "table_size_warnings": warnings,
            "meta_table": sink.get_meta(),
        },
        out_path=summary_path,
        previous_from=[RESULTS_DIR / SUMMARY_NAME],
        extra={"summary_kind": "canonical" if canonical else "ad-hoc"},
    )
    print(f"[dashboard] wrote {_rel(summary_path)} ({why})")

    if args.once:
        print("[dashboard] --once: not serving")
        return 0
    try:
        serve(
            sink,
            port=args.port,
            host=args.host,
            allowed_origins=args.allow_origin,
            npm_dir=args.npm_dir,
        )
    except KeyboardInterrupt:
        print("\n[dashboard] stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
