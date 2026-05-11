"""Tk-side dispatcher that polls the request queue and shows dialogs.

Driven by `root.after(POLL_MS, _tick)` so all widget creation happens on the
Tk main thread.
"""
from __future__ import annotations

import time
from typing import Any, Callable

import customtkinter as ctk

from .dialogs.choice_dialog import ChoiceDialog
from .dialogs.confirm_dialog import ConfirmDialog
from .dialogs.file_dialog import FileDialog
from .dialogs.form_dialog import FormDialog
from .dialogs.text_dialog import TextDialog
from .queue import Request, RequestQueue

POLL_MS = 50

_DIALOG_BY_TYPE = {
    "text": TextDialog,
    "choice": ChoiceDialog,
    "confirm": ConfirmDialog,
    "file": FileDialog,
    "form": FormDialog,
}


def _build_response(req: Request, status: str, value: Any, user_note: str) -> dict[str, Any]:
    from datetime import datetime, timezone
    return {
        "status": status,
        "live": True,
        "value": value,
        "user_note": user_note or "",
        "answered_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_ms": int((time.time() - req.submitted_at) * 1000),
        "request_id": req.request_id,
        "type": req.type,
    }


class Dispatcher:
    def __init__(self, root: ctk.CTk, queue: RequestQueue, logger,
                 on_pending_change: Callable[[int], None] | None = None) -> None:
        self.root = root
        self.queue = queue
        self.log = logger
        self.on_pending_change = on_pending_change
        self._current_dialog = None
        self._last_pending = -1

    def start(self) -> None:
        self.root.after(POLL_MS, self._tick)

    def _tick(self) -> None:
        # Notify tray of pending count changes.
        n = self.queue.pending_count()
        if n != self._last_pending and self.on_pending_change:
            try:
                self.on_pending_change(n)
            except Exception as exc:  # noqa: BLE001
                self.log.debug("on_pending_change failed: %s", exc)
            self._last_pending = n

        if self._current_dialog is None:
            req = self.queue.pop()
            if req is not None:
                self._show(req)
        self.root.after(POLL_MS, self._tick)

    def _show(self, req: Request) -> None:
        dialog_cls = _DIALOG_BY_TYPE.get(req.type)
        if dialog_cls is None:
            self.log.error("unknown dialog type %r", req.type)
            req.response = _build_response(req, "cancelled", None, "")
            req.response["error"] = f"unknown type {req.type!r}"
            req.response["live"] = False
            req.event.set()
            return

        def _on_done(status: str, value: Any, user_note: str) -> None:
            req.response = _build_response(req, status, value, user_note)
            req.event.set()
            self._current_dialog = None
            self.log.info("dialog closed id=%s status=%s elapsed=%dms",
                          req.request_id, status, req.response["elapsed_ms"])

        try:
            self._current_dialog = dialog_cls(
                self.root,
                req=req,
                on_done=_on_done,
                logger=self.log,
            )
            self.log.info("dialog open id=%s type=%s", req.request_id, req.type)
        except Exception as exc:  # noqa: BLE001
            self.log.exception("dialog creation failed: %s", exc)
            req.response = _build_response(req, "cancelled", None, "")
            req.response["error"] = f"{type(exc).__name__}: {exc}"
            req.response["live"] = False
            req.event.set()
            self._current_dialog = None
