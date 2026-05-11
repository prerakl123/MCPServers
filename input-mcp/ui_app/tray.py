"""pystray icon thread.

Runs on a background thread (`pystray.Icon.run` blocks). Tk lives on the main
thread; we never touch widgets from here. To close the dispatcher / Tk root
on Quit, we set the shared shutdown_event which the main loop watches.
"""
from __future__ import annotations

import threading

import pystray

from . import icon as _icon
from .queue import RequestQueue


class TrayController:
    def __init__(self, queue: RequestQueue, shutdown_event: threading.Event,
                 logger) -> None:
        self.queue = queue
        self.shutdown_event = shutdown_event
        self.log = logger
        self._icon: pystray.Icon | None = None
        self._idle = _icon.idle_icon()
        self._active = _icon.active_icon()

    def _build_menu(self) -> pystray.Menu:
        n = self.queue.pending_count()
        return pystray.Menu(
            pystray.MenuItem(
                f"Pending requests: {n}",
                action=lambda *_: None,
                enabled=False,
            ),
            pystray.MenuItem("Cancel all pending", self._on_cancel_all),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit),
        )

    def _on_cancel_all(self, *_args) -> None:
        cancelled = self.queue.cancel_all()
        self.log.info("tray: cancelling %d pending requests", len(cancelled))
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
                    "cancel_source": "tray",
                }
            req.event.set()

    def _on_quit(self, *_args) -> None:
        self.log.info("tray: quit requested")
        self._on_cancel_all()
        self.shutdown_event.set()
        if self._icon:
            self._icon.stop()

    def update_pending(self, n: int) -> None:
        if not self._icon:
            return
        try:
            self._icon.icon = self._active if n > 0 else self._idle
            self._icon.title = f"input-mcp UI service — {n} pending"
            self._icon.menu = self._build_menu()
        except Exception as exc:  # noqa: BLE001
            self.log.debug("tray update failed: %s", exc)

    def run_in_thread(self) -> threading.Thread:
        self._icon = pystray.Icon(
            "input-mcp",
            self._idle,
            "input-mcp UI service — 0 pending",
            menu=self._build_menu(),
        )
        thread = threading.Thread(target=self._icon.run, name="pystray", daemon=True)
        thread.start()
        return thread
