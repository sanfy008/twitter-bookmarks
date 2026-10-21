# ruff: noqa: RUF001
"""Serve only the userscript so Violentmonkey can install it with one click.

This intentionally does NOT expose the project directory over HTTP. Only two
routes exist: an informational page and the userscript itself. The server binds
to loopback on an ephemeral port, validates the Host header, and shuts down a
few seconds after the script has been downloaded.
"""

from __future__ import annotations

import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

SCRIPT_PATH = Path(__file__).resolve().parent / "x-archive-sync.user.js"
SCRIPT_ROUTE = "/x-archive-sync.user.js"
GRACE_SECONDS = 5
MAX_SECONDS = 60

LANDING_PAGE = """<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><title>x-archive userscript</title>
<body style="font-family:system-ui;max-width:40rem;margin:4rem auto;line-height:1.6">
<h1>x-archive userscript</h1>
<p>如果浏览器没有自动弹出安装窗口，请点击
<a href="/x-archive-sync.user.js">安装 x-archive-sync.user.js</a>。</p>
<p>需要先安装 Violentmonkey 或 Tampermonkey。安装完成后请关闭本页。</p>
</body></html>"""


class UserScriptHandler(BaseHTTPRequestHandler):
    server_version = "x-archive-installer"

    def do_GET(self) -> None:
        if self.headers.get("Host") not in self.server.allowed_hosts:
            self.send_error(403, "forbidden host")
            return

        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", LANDING_PAGE.encode("utf-8"))
            return
        if path != SCRIPT_ROUTE:
            self.send_error(404, "not found")
            return
        if not SCRIPT_PATH.is_file():
            self.send_error(500, "userscript file is missing")
            return

        self._send(
            200,
            "application/javascript; charset=utf-8",
            SCRIPT_PATH.read_bytes(),
            download=True,
        )
        self.server.served = True

    def _send(self, status: int, content_type: str, body: bytes, *, download: bool = False) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if download:
            self.send_header("Content-Disposition", 'inline; filename="x-archive-sync.user.js"')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write(f"[installer] {args[0]} {args[1]}\n")


def serve_and_open() -> int:
    if not SCRIPT_PATH.is_file():
        print(f"error: userscript not found: {SCRIPT_PATH}", file=sys.stderr)
        return 2

    server = ThreadingHTTPServer(("127.0.0.1", 0), UserScriptHandler)
    server.daemon_threads = True
    server.timeout = 1.0
    port = server.server_address[1]
    server.allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    server.served = False

    target_url = f"http://127.0.0.1:{port}{SCRIPT_ROUTE}"
    print(f"[x-archive] Serving userscript at {target_url}")
    print("[x-archive] Opening the default browser for one-click installation...")
    webbrowser.open(target_url)

    deadline = time.monotonic() + MAX_SECONDS
    served_at: float | None = None
    try:
        while time.monotonic() < deadline:
            server.handle_request()
            if server.served and served_at is None:
                served_at = time.monotonic()
            if served_at is not None and time.monotonic() - served_at >= GRACE_SECONDS:
                break
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

    if not server.served:
        print(
            "[x-archive] The userscript was never requested. Open the URL manually if needed.",
            file=sys.stderr,
        )
        return 1
    print("[x-archive] Installer server stopped cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(serve_and_open())
