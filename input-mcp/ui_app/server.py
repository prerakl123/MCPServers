"""ThreadingHTTPServer that exposes the localhost UI service.

Endpoints:
  POST /ask           — submit a request, block until user acts or timeout
  GET  /health        — liveness check
  GET  /pending       — list pending requests
  POST /cancel/<id>   — cancel a queued/showing request
  POST /shutdown      — graceful exit
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .queue import Request, RequestQueue


class _Context:
    """Shared state passed to the handler via the server attribute."""

    def __init__(self, queue: RequestQueue, token: str, version: str,
                 started_at: float, shutdown_event: threading.Event,
                 logger):
        self.queue = queue
        self.token = token
        self.version = version
        self.started_at = started_at
        self.shutdown_event = shutdown_event
        self.log = logger


class _Handler(BaseHTTPRequestHandler):
    server_version = "input-mcp-ui/0.1"

    @property
    def ctx(self) -> _Context:
        return self.server.ctx  # type: ignore[attr-defined]

    # silence default access logging — we use the project logger
    def log_message(self, format, *args):  # noqa: A002
        self.ctx.log.debug("http %s - %s", self.address_string(), format % args)

    def _read_json(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            self.ctx.log.warning("invalid JSON body: %s", exc)
            return None

    def _send_json(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _check_auth(self) -> bool:
        header = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not header.startswith(prefix):
            return False
        return header[len(prefix):].strip() == self.ctx.token

    # ------------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        if not self._check_auth():
            self._send_json(401, {"error": "unauthorized"})
            return

        if self.path == "/health":
            self._send_json(200, {
                "ok": True,
                "version": self.ctx.version,
                "pending_count": self.ctx.queue.pending_count(),
                "uptime_sec": round(time.time() - self.ctx.started_at, 2),
            })
            return

        if self.path == "/pending":
            self._send_json(200, {"pending": self.ctx.queue.pending_ids()})
            return

        self._send_json(404, {"error": f"unknown path {self.path}"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._check_auth():
            self._send_json(401, {"error": "unauthorized"})
            return

        if self.path == "/ask":
            self._handle_ask()
            return
        if self.path.startswith("/cancel/"):
            request_id = self.path.split("/", 2)[-1]
            self._handle_cancel(request_id)
            return
        if self.path == "/shutdown":
            self.ctx.log.info("shutdown requested via HTTP")
            self._send_json(200, {"ok": True})
            self.ctx.shutdown_event.set()
            return

        self._send_json(404, {"error": f"unknown path {self.path}"})

    # ------------------------------------------------------------------
    def _handle_ask(self) -> None:
        body = self._read_json()
        if body is None:
            self._send_json(400, {"error": "invalid JSON"})
            return

        type_ = body.get("type")
        if type_ not in {"text", "choice", "confirm", "file", "form"}:
            self._send_json(400, {"error": f"unknown type {type_!r}"})
            return

        timeout_sec = max(1, min(int(body.get("timeout_sec") or 300), 3600))
        req = Request(
            type=type_,
            prompt=str(body.get("prompt") or ""),
            spec=dict(body.get("spec") or {}),
            timeout_sec=timeout_sec,
            origin=str(body.get("origin") or "unknown"),
        )
        if body.get("request_id"):
            req.request_id = str(body["request_id"])

        self.ctx.log.info("ask submit id=%s type=%s origin=%s timeout=%ds",
                          req.request_id, req.type, req.origin, req.timeout_sec)

        self.ctx.queue.submit(req)

        # Block until the dispatcher / dialog signals completion, OR until
        # the per-request timeout — the dispatcher itself enforces timeout
        # once the dialog is shown, but we cap the total wait here as a
        # safety net (queue wait + dialog wait).
        wait_budget = req.timeout_sec + 30  # +30s for queue overhead
        signaled = req.event.wait(timeout=wait_budget)

        if not signaled or req.response is None:
            self.ctx.log.warning("ask id=%s server-side wait expired", req.request_id)
            self.ctx.queue.mark_done(req.request_id)
            self._send_json(200, {
                "status": "timed_out",
                "live": False,
                "value": None,
                "user_note": "",
                "answered_at": None,
                "elapsed_ms": int((time.time() - req.submitted_at) * 1000),
                "request_id": req.request_id,
                "type": req.type,
                "error": "ui_dispatch_timeout",
            })
            return

        self.ctx.queue.mark_done(req.request_id)
        self._send_json(200, req.response)

    def _handle_cancel(self, request_id: str) -> None:
        req = self.ctx.queue.cancel(request_id)
        if not req:
            self._send_json(404, {"error": f"no such request {request_id}"})
            return
        if req.response is None:
            req.response = {
                "status": "cancelled",
                "live": True,
                "value": None,
                "user_note": "",
                "answered_at": None,
                "elapsed_ms": int((time.time() - req.submitted_at) * 1000),
                "request_id": req.request_id,
                "type": req.type,
                "cancel_source": "external",
            }
        req.event.set()
        self._send_json(200, {"ok": True, "request_id": request_id})


class _SingleInstanceHTTPServer(ThreadingHTTPServer):
    """Refuse to share the port with another process.

    Default Python sets allow_reuse_address=True, which on Windows means a
    second bind on the same port silently succeeds — leading to multiple
    ui_app instances clobbering each other. We force exclusive use; second
    invocation will fail with a clear OSError on bind.
    """

    allow_reuse_address = False
    daemon_threads = True


def start_http_server(host: str, port: int, ctx: _Context) -> ThreadingHTTPServer:
    server = _SingleInstanceHTTPServer((host, port), _Handler)
    server.ctx = ctx  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, name="http-server", daemon=True)
    thread.start()
    return server


__all__ = ["_Context", "start_http_server"]
