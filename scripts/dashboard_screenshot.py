#!/usr/bin/env python
"""Reproduce ``results/figures/dashboard_screenshot.png`` from the repository.

What it does, all in one process:

1. loads the replay the dashboard CLI would serve (``results/execution_*.csv``,
   or the synthetic demo with ``--demo``) into a ``PerspectiveSink``;
2. starts the real dashboard in-process with
   ``quantstack.dashboard.server.BackgroundDashboard`` (daemon thread, own
   asyncio loop, OS-assigned port on 127.0.0.1);
3. launches a headless Chromium and drives it over the DevTools protocol with
   Tornado's websocket client (no playwright Python package needed);
4. waits until the page's status line reads ``connected: ws://...`` and both
   ``<perspective-viewer>`` elements have flushed, saves a PNG and exits.

Requirements
------------
* A Chromium/Chrome binary: ``--chrome``, ``$QUANTSTACK_CHROMIUM``, the
  Playwright-managed Chromium under ``/opt/pw-browsers`` or
  ``~/.cache/ms-playwright`` (already installed here; do not run
  ``playwright install``), or ``chromium``/``google-chrome`` on ``PATH``.
* The pinned ``@perspective-dev/*`` 5.5.1 JavaScript.  ``static/index.html``
  loads it from cdn.jsdelivr.net, so with ``--js-source cdn`` the *browser*
  must be able to reach jsdelivr.  Where it cannot (this project's sandbox
  only reaches PyPI and the npm registry), ``--js-source local`` serves the
  byte-identical npm tarballs from the dashboard itself (its ``npm_dir``
  option: only the jsdelivr prefix of the page is rewritten, the versions are
  checked against the page's pins): from ``--npm-dir DIR`` if given
  (``DIR/client/package/...``, ``DIR/viewer/package/...``, ...), otherwise
  downloaded once from registry.npmjs.org into ``--npm-cache`` (default
  ``~/.cache/quantstack/perspective-npm/<version>``) and verified against the
  registry's sha512 integrity.  ``--js-source auto`` (the default) uses the
  CDN when this machine can reach it and local assets otherwise.

Usage::

    python scripts/dashboard_screenshot.py                  # -> results/figures/dashboard_screenshot.png
    python scripts/dashboard_screenshot.py --demo --out /tmp/demo.png
    python scripts/dashboard_screenshot.py --js-source local --npm-dir ~/npm/perspective-5.5.1

Exit status: 0 screenshot saved with the page connected; 1 the page did not
connect (the PNG is still saved, for diagnosis); 3 no Chromium found; 4 the
JavaScript assets are unavailable.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import glob
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import perspective  # noqa: E402
import tornado.websocket  # noqa: E402

from quantstack.dashboard import server as ds  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "results" / "figures" / "dashboard_screenshot.png"
NPM_REGISTRY = "https://registry.npmjs.org"
CDN = "https://cdn.jsdelivr.net/npm"
CHROMIUM_GLOBS = (
    "/opt/pw-browsers/chromium-*/chrome-linux/chrome",
    "/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell",
    str(Path.home() / ".cache/ms-playwright/chromium-*/chrome-linux/chrome"),
)


class AssetsUnavailable(RuntimeError):
    """Neither the CDN nor local npm packages can provide the page's JS."""


# --------------------------------------------------------------------------
# Locating Chromium and the JavaScript
# --------------------------------------------------------------------------


def find_chromium(explicit: str | None = None) -> str | None:
    candidates = [explicit, os.environ.get("QUANTSTACK_CHROMIUM")]
    for pattern in CHROMIUM_GLOBS:
        candidates += sorted(glob.glob(pattern), reverse=True)
    candidates += [shutil.which(n) for n in ("chromium", "chromium-browser", "google-chrome", "chrome")]
    for c in candidates:
        if c and Path(c).is_file() and os.access(c, os.X_OK):
            return c
    return None


def _pins() -> dict[str, str]:
    """``{"@perspective-dev/client": "5.5.1", ...}`` as pinned by index.html."""
    pins = ds.npm_pins_in_index_html()
    bad = {k: v for k, v in pins.items() if len(v) != 1}
    if bad or not pins:
        raise AssetsUnavailable(f"index.html pins are ambiguous or missing: {pins}")
    return {k: v[0] for k, v in pins.items()}


def cdn_reachable(timeout: float = 5.0) -> bool:
    package, version = next(iter(_pins().items()))
    request = urllib.request.Request(f"{CDN}/{package}@{version}/package.json", method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001 -- any failure means "not reachable"
        return False


def _package_ok(root: Path, package: str, version: str) -> bool:
    manifest = root / "package" / "package.json"
    try:
        meta = json.loads(manifest.read_text())
    except (OSError, ValueError):
        return False
    return meta.get("name") == package and meta.get("version") == version


def ensure_npm_packages(cache_dir: Path, timeout: float = 60.0) -> Path:
    """Download + unpack the page's pinned packages into ``cache_dir`` (the
    layout ``make_app(npm_dir=...)`` expects) unless already there."""
    cache_dir = Path(cache_dir)
    for package, version in _pins().items():
        short = package.split("/", 1)[1]
        target = cache_dir / short
        if _package_ok(target, package, version):
            continue
        meta_url = f"{NPM_REGISTRY}/{package}/{version}"
        try:
            with urllib.request.urlopen(meta_url, timeout=timeout) as resp:
                dist = json.load(resp)["dist"]
            with urllib.request.urlopen(dist["tarball"], timeout=timeout) as resp:
                blob = resp.read()
        except Exception as exc:  # noqa: BLE001
            raise AssetsUnavailable(f"could not download {package}@{version}: {exc}") from exc
        integrity = dist.get("integrity", "")
        if integrity.startswith("sha512-"):
            digest = base64.b64encode(hashlib.sha512(blob).digest()).decode()
            if digest != integrity.split("-", 1)[1]:
                raise AssetsUnavailable(f"{package}@{version}: tarball fails its sha512 integrity check")
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix=f".{short}-", dir=cache_dir))  # same fs: atomic move
        try:
            with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
                tar.extractall(tmp, filter="data")
            if target.exists():
                shutil.rmtree(target)
            tmp.rename(target)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if not _package_ok(target, package, version):
            raise AssetsUnavailable(f"{target} does not contain {package}@{version} after unpacking")
    return cache_dir


def default_npm_cache() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "quantstack" / "perspective-npm" / perspective.__version__


def resolve_npm_dir(js_source: str = "auto", npm_dir: str | Path | None = None,
                    npm_cache: str | Path | None = None) -> Path | None:
    """``None`` = let the browser use the CDN; else a local npm dir to serve."""
    if js_source not in ("auto", "cdn", "local"):
        raise ValueError(f"js_source must be auto/cdn/local, not {js_source!r}")
    if js_source == "cdn":
        return None
    if npm_dir is not None:
        pins = _pins()
        missing = [p for p, v in pins.items() if not _package_ok(Path(npm_dir) / p.split("/", 1)[1], p, v)]
        if missing:
            raise AssetsUnavailable(f"--npm-dir {npm_dir} lacks {missing} at the pinned version")
        return Path(npm_dir)
    if js_source == "auto" and cdn_reachable():
        return None
    return ensure_npm_packages(Path(npm_cache) if npm_cache else default_npm_cache())


# --------------------------------------------------------------------------
# Chromium over the DevTools protocol
# --------------------------------------------------------------------------


def _launch_chromium(chrome: str, profile_dir: str, width: int, height: int):
    """Start headless Chromium on a free DevTools port; return (proc, ws_url, log)."""
    env = dict(os.environ)
    # Chromium puts its singleton UNIX socket under $TMPDIR; socket paths are
    # capped at ~108 bytes and a long TMPDIR makes it abort (SIGTRAP) before
    # DevTools starts. Fall back to the system default for the child only.
    if len(env.get("TMPDIR", "")) > 60:
        env.pop("TMPDIR")
    proc = subprocess.Popen(
        [
            chrome, "--headless=new", "--no-sandbox", "--disable-dev-shm-usage",
            "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
            "--no-first-run", "--no-default-browser-check", "--hide-scrollbars",
            "--remote-debugging-port=0", "--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={profile_dir}", f"--window-size={width},{height}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, env=env,
    )
    log: list[str] = []
    found = threading.Event()
    holder: dict = {}

    def drain() -> None:  # keep reading, or Chromium blocks on a full pipe
        for line in proc.stderr:
            log.append(line.rstrip())
            del log[:-200]
            if "DevTools listening on " in line and not found.is_set():
                holder["ws"] = line.split("DevTools listening on ", 1)[1].strip()
                found.set()
        found.set()

    threading.Thread(target=drain, daemon=True).start()
    if not found.wait(30) or "ws" not in holder:
        proc.kill()
        raise RuntimeError(
            f"Chromium did not start a DevTools endpoint (exit {proc.poll()}):\n"
            + "\n".join(log[-20:])
        )
    return proc, holder["ws"], log


class _Cdp:
    def __init__(self, conn) -> None:
        self.conn, self.next_id, self.waiting, self.events = conn, 0, {}, []
        self.reader = asyncio.ensure_future(self._read())

    async def _read(self) -> None:
        while True:
            raw = await self.conn.read_message()
            if raw is None:
                for fut in self.waiting.values():
                    fut.cancel()
                return
            msg = json.loads(raw)
            if "id" in msg and msg["id"] in self.waiting:
                self.waiting.pop(msg["id"]).set_result(msg)
            elif "method" in msg:
                self.events.append(msg)

    async def call(self, method: str, session: str | None = None, timeout: float = 60.0, **params):
        self.next_id += 1
        fut = asyncio.get_running_loop().create_future()
        self.waiting[self.next_id] = fut
        payload = {"id": self.next_id, "method": method, "params": params}
        if session:
            payload["sessionId"] = session
        await self.conn.write_message(json.dumps(payload))
        msg = await asyncio.wait_for(fut, timeout)
        if "error" in msg:
            raise RuntimeError(f"{method}: {msg['error']}")
        return msg.get("result", {})

    async def evaluate(self, session: str, expression: str, timeout: float = 60.0):
        res = await self.call(
            "Runtime.evaluate", session, timeout=timeout,
            expression=expression, awaitPromise=True, returnByValue=True,
        )
        if "exceptionDetails" in res:
            raise RuntimeError(f"page JS failed: {json.dumps(res['exceptionDetails'])[:500]}")
        return res.get("result", {}).get("value")

    def console(self) -> list[str]:
        out = []
        for e in self.events:
            p = e.get("params", {})
            if e["method"] == "Runtime.consoleAPICalled":
                out.append(p["type"] + ": " + " ".join(str(a.get("value", a.get("description", ""))) for a in p["args"])[:300])
            elif e["method"] == "Runtime.exceptionThrown":
                out.append("exception: " + json.dumps(p.get("exceptionDetails", {}))[:300])
            elif e["method"] == "Log.entryAdded":
                entry = p["entry"]
                out.append(f"log.{entry['level']}: {entry['text'][:300]} {entry.get('url', '')}".rstrip())
        return out


_STATUS_JS = "document.getElementById('status') ? document.getElementById('status').textContent : null"
_FLUSH_JS = """(async () => {
  const viewers = [...document.querySelectorAll('perspective-viewer')];
  const t = new Promise((r) => setTimeout(() => r('timeout'), 20000));
  const done = await Promise.race([Promise.all(viewers.map((v) => v.flush())).then(() => 'ok'), t]);
  return {flush: done, viewers: viewers.length,
          banner_visible: !document.getElementById('demo-banner').hidden,
          banner_text: document.getElementById('demo-banner').textContent.replace(/\\s+/g, ' ').trim(),
          source_text: document.getElementById('source').textContent};
})()"""


async def _drive(ws_url: str, page_url: str, out_png: Path, wait_s: float, width: int, height: int) -> dict:
    conn = await tornado.websocket.websocket_connect(ws_url, max_message_size=256 * 1024 * 1024)
    cdp = _Cdp(conn)
    try:
        target = await cdp.call("Target.createTarget", url="about:blank")
        session = (await cdp.call("Target.attachToTarget", targetId=target["targetId"], flatten=True))["sessionId"]
        for method in ("Runtime.enable", "Log.enable", "Page.enable"):
            await cdp.call(method, session)
        await cdp.call("Emulation.setDeviceMetricsOverride", session, width=width, height=height,
                       deviceScaleFactor=1, mobile=False)
        t0 = time.monotonic()
        await cdp.call("Page.navigate", session, url=page_url)
        status = None
        while time.monotonic() - t0 < wait_s:
            status = await cdp.evaluate(session, _STATUS_JS)
            if status and (status.startswith("connection failed")
                           or (status.startswith("connected:") and "loading" not in status)):
                break
            await asyncio.sleep(0.25)
        connected = bool(status and status.startswith("connected:") and "loading" not in status)
        page = await cdp.evaluate(session, _FLUSH_JS, timeout=30) if connected else {}
        await asyncio.sleep(1.0)  # let the chart's canvas paint after flush()
        shot = await cdp.call("Page.captureScreenshot", session, format="png")
        out_png.parent.mkdir(parents=True, exist_ok=True)
        out_png.write_bytes(base64.b64decode(shot["data"]))
        return {
            "status": status,
            "connected": connected,
            "seconds_to_status": round(time.monotonic() - t0, 1),
            **(page or {}),
            "console": cdp.console(),
        }
    finally:
        cdp.reader.cancel()
        conn.close()


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


def capture(
    out_png: str | Path = DEFAULT_OUT,
    *,
    demo: bool = False,
    js_source: str = "auto",
    npm_dir: str | Path | None = None,
    npm_cache: str | Path | None = None,
    chrome: str | None = None,
    wait_s: float = 90.0,
    width: int = 1280,
    height: int = 900,
    profile_dir: str | Path | None = None,
) -> dict:
    """Serve the dashboard in-process, screenshot it, return what happened.

    ``profile_dir``: Chromium user-data dir to use (default: a fresh
    temporary directory, removed afterwards)."""
    chrome = find_chromium(chrome)
    if chrome is None:
        raise FileNotFoundError("no Chromium/Chrome binary found (see --chrome)")
    local = resolve_npm_dir(js_source, npm_dir, npm_cache)
    data = (
        ds.demo_replay("forced by scripts/dashboard_screenshot.py --demo")
        if demo
        else ds.load_replay(ds.DEFAULT_EQUITY_CSV, ds.DEFAULT_POSITIONS_CSV, ds.DEFAULT_FILLS_CSV)
    )
    sink = ds.PerspectiveSink()
    ds.populate_sink(sink, data)
    out_png = Path(out_png)
    with contextlib.ExitStack() as stack:
        if profile_dir is None:
            profile = stack.enter_context(tempfile.TemporaryDirectory(prefix="quantstack-chrome-"))
        else:
            Path(profile_dir).mkdir(parents=True, exist_ok=True)
            profile = str(profile_dir)
        dash = stack.enter_context(ds.BackgroundDashboard(sink, port=0, npm_dir=local).start())
        proc, ws_url, _chrome_log = _launch_chromium(chrome, profile, width, height)
        try:
            result = asyncio.run(_drive(ws_url, dash.url, out_png, wait_s, width, height))
        finally:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()
    result.update(
        png=ds._rel(out_png),
        chromium=chrome,
        js_source="cdn" if local is None else f"local npm packages ({local})",
        data_source=sink.get_meta().get("data_source"),
        table_sizes=sink.table_sizes(),
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="PNG to write (default: %(default)s)")
    parser.add_argument("--demo", action="store_true", help="serve the synthetic demo data (shows the DEMO banner)")
    parser.add_argument("--js-source", choices=("auto", "cdn", "local"), default="auto")
    parser.add_argument("--npm-dir", default=None, help="unpacked npm packages (DIR/client/package/...)")
    parser.add_argument("--npm-cache", default=None, help="download cache for --js-source local/auto")
    parser.add_argument("--chrome", default=None, help="Chromium/Chrome binary")
    parser.add_argument("--wait", type=float, default=90.0, help="seconds to wait for 'connected'")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--profile-dir", default=None, help="Chromium user-data dir (default: a temp dir)")
    args = parser.parse_args(argv)
    try:
        result = capture(
            args.out, demo=args.demo, js_source=args.js_source, npm_dir=args.npm_dir,
            npm_cache=args.npm_cache, chrome=args.chrome, wait_s=args.wait,
            width=args.width, height=args.height, profile_dir=args.profile_dir,
        )
    except FileNotFoundError as exc:
        print(f"[screenshot] {exc}", file=sys.stderr)
        return 3
    except AssetsUnavailable as exc:
        print(f"[screenshot] JavaScript unavailable: {exc}", file=sys.stderr)
        return 4
    print(json.dumps(result, indent=2))
    if not result["connected"]:
        print(f"[screenshot] page did not connect: {result['status']!r}", file=sys.stderr)
        return 1
    print(f"[screenshot] wrote {result['png']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
