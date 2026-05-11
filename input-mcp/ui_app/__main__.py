"""Entry point: `python -m ui_app --port N --token-file PATH --parent-pid PID`."""
from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
import time
from pathlib import Path

import customtkinter as ctk
import httpx

from tools._logging import get_ui_logger

from . import __version__, theme
from .dispatcher import Dispatcher
from .queue import RequestQueue
from .server import _Context, start_http_server
from .tray import TrayController

log = get_ui_logger()


def _existing_ui_healthy(host: str, port: int, token: str, timeout: float = 1.5) -> bool:
    """Return True if a ui_app is already responding to /health on this port.

    Used at startup to refuse a second instance instead of stacking.
    """
    try:
        r = httpx.get(
            f"http://{host}:{port}/health",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
        return r.status_code == 200 and bool(r.json().get("ok"))
    except Exception:
        return False


def _parent_alive(pid: int) -> bool:
    if pid <= 0:
        return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _shutdown(root: ctk.CTk, server, tray: TrayController, queue: RequestQueue) -> None:
    log.info("ui_app shutting down")
    # Cancel any in-flight requests so HTTP clients get a clean response.
    cancelled = queue.cancel_all()
    for req in cancelled:
        if req.response is None:
            req.response = {
                "status": "cancelled",
                "live": True,
                "value": None,
                "user_note": "",
                "answered_at": None,
                "elapsed_ms": 0,
                "request_id": req.request_id,
                "type": req.type,
                "cancel_source": "shutdown",
            }
        req.event.set()

    try:
        server.shutdown()
    except Exception as exc:  # noqa: BLE001
        log.debug("server.shutdown failed: %s", exc)
    try:
        if tray._icon:  # type: ignore[attr-defined]
            tray._icon.stop()  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(prog="ui_app")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--token-file", type=str, required=True)
    parser.add_argument("--parent-pid", type=int, default=0)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    args = parser.parse_args()

    token = Path(args.token_file).read_text(encoding="utf-8").strip()
    if not token:
        log.error("token file %s is empty", args.token_file)
        sys.exit(2)

    log.info("ui_app starting host=%s port=%d parent_pid=%d", args.host, args.port, args.parent_pid)

    # Single-instance guard: if another ui_app is already on this port and
    # responding to /health with our token, don't stack a second copy.
    if _existing_ui_healthy(args.host, args.port, token):
        log.warning("ui_app already healthy on %s:%d — exiting (one instance only)",
                    args.host, args.port)
        print(f"ui_app already running on {args.host}:{args.port}", file=sys.stderr)
        sys.exit(0)

    theme.configure()
    root = ctk.CTk()
    root.withdraw()  # invisible — only dialogs appear
    root.title("input-mcp UI service")

    queue = RequestQueue()
    shutdown_event = threading.Event()

    ctx = _Context(
        queue=queue,
        token=token,
        version=__version__,
        started_at=time.time(),
        shutdown_event=shutdown_event,
        logger=log,
    )

    try:
        server = start_http_server(args.host, args.port, ctx)
    except OSError as exc:
        log.error("could not bind %s:%d — %s", args.host, args.port, exc)
        print(f"port {args.port} unavailable: {exc}", file=sys.stderr)
        sys.exit(2)
    log.info("http server listening on %s:%d", args.host, args.port)

    # Ctrl+C / Ctrl+Break: signal a graceful shutdown rather than letting Tk
    # swallow the signal. The watchdog polls shutdown_event every 2 seconds.
    def _on_signal(signum, _frame):
        log.info("received signal %s — shutting down", signum)
        shutdown_event.set()

    try:
        signal.signal(signal.SIGINT, _on_signal)
        if hasattr(signal, "SIGBREAK"):  # Windows Ctrl+Break
            signal.signal(signal.SIGBREAK, _on_signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _on_signal)
    except (ValueError, OSError) as exc:
        log.debug("could not install signal handler: %s", exc)

    tray = TrayController(queue, shutdown_event, log)
    tray.run_in_thread()

    dispatcher = Dispatcher(root, queue, log, on_pending_change=tray.update_pending)
    dispatcher.start()

    # Watchdogs: shutdown_event polled every 200ms, parent every 10s.
    def _watchdog():
        if shutdown_event.is_set():
            _shutdown(root, server, tray, queue)
            return
        if args.parent_pid and not _parent_alive(args.parent_pid):
            log.warning("parent pid %d gone — shutting down", args.parent_pid)
            shutdown_event.set()
        root.after(2000, _watchdog)

    root.after(2000, _watchdog)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        _shutdown(root, server, tray, queue)
        log.info("ui_app exited")


if __name__ == "__main__":
    main()
