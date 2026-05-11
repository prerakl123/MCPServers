"""Thin wrappers that build the per-type spec and call the UI directly."""
from __future__ import annotations

import time
from typing import Any

import customtkinter as ctk

from ._logging import get_logger
from ui_app import theme
from ui_app.queue import Request
from ui_app.dialogs.text_dialog import TextDialog
from ui_app.dialogs.choice_dialog import ChoiceDialog
from ui_app.dialogs.confirm_dialog import ConfirmDialog
from ui_app.dialogs.file_dialog import FileDialog
from ui_app.dialogs.form_dialog import FormDialog

log = get_logger("prompts")

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


class Prompts:
    def __init__(self, client: Any = None) -> None:
        self.client = client
        try:
            theme.configure()
        except Exception as e:
            log.warning("Theme configuration failed: %s", e)

    def _show_dialog(self, type_: str, prompt: str, spec: dict[str, Any], timeout_sec: int) -> dict[str, Any]:
        root = ctk.CTk()
        root.withdraw()
        
        req = Request(type=type_, prompt=prompt, spec=spec, timeout_sec=timeout_sec, origin="input-mcp")
        response = None
        
        def on_done(status: str, value: Any, user_note: str) -> None:
            nonlocal response
            response = _build_response(req, status, value, user_note)
            try:
                root.quit()
            except Exception:
                pass

        dialog_cls = {
            "text": TextDialog,
            "choice": ChoiceDialog,
            "confirm": ConfirmDialog,
            "file": FileDialog,
            "form": FormDialog,
        }.get(type_)
        
        if not dialog_cls:
            return {"status": "error", "error": f"unknown type {type_}"}
            
        try:
            dialog_cls(root, req, on_done, log)
            root.mainloop()
        except Exception as exc:
            log.exception("Dialog failed")
            return {"status": "error", "error": str(exc)}
        finally:
            try:
                root.destroy()
            except Exception:
                pass
                
        return response or {"status": "error", "error": "Dialog closed without response"}

    def ask_text(self, question: str, default: str = "", multiline: bool = False,
                 placeholder: str = "", timeout_sec: int = 300,
                 regex_validate: str | None = None) -> dict[str, Any]:
        spec: dict[str, Any] = {"default": default, "multiline": multiline}
        if placeholder:
            spec["placeholder"] = placeholder
        if regex_validate:
            spec["regex_validate"] = regex_validate
        return self._show_dialog("text", question, spec, timeout_sec)

    def ask_choice(self, question: str, options: list[Any],
                   multi_select: bool = False, allow_other: bool = True,
                   timeout_sec: int = 300) -> dict[str, Any]:
        spec = {
            "options": options,
            "multi_select": multi_select,
            "allow_other": allow_other,
        }
        return self._show_dialog("choice", question, spec, timeout_sec)

    def ask_confirm(self, question: str, confirm_label: str = "Yes",
                    deny_label: str = "No", default: str | None = None,
                    timeout_sec: int = 300) -> dict[str, Any]:
        spec = {
            "confirm_label": confirm_label,
            "deny_label": deny_label,
            "default": default,
        }
        return self._show_dialog("confirm", question, spec, timeout_sec)

    def ask_file(self, question: str, mode: str = "open",
                 filters: list[dict] | None = None,
                 multiple: bool = False, timeout_sec: int = 300) -> dict[str, Any]:
        if mode not in ("open", "save", "directory"):
            raise ValueError(f"mode must be open|save|directory, got {mode!r}")
        spec = {
            "mode": mode,
            "filters": filters or [],
            "multiple": bool(multiple),
        }
        return self._show_dialog("file", question, spec, timeout_sec)

    def ask_form(self, title: str, fields: list[dict],
                 timeout_sec: int = 600) -> dict[str, Any]:
        if not fields:
            raise ValueError("fields must be a non-empty list")
        spec = {"title": title, "fields": fields}
        return self._show_dialog("form", title, spec, timeout_sec)

    def list_pending_requests(self) -> dict[str, Any]:
        return {"pending": []}

