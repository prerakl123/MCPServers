"""Common dialog scaffolding: title bar, prompt, footer, countdown, user_note.

Each concrete dialog subclasses BaseDialog and fills in `_build_body()` plus
`_collect_value()`. BaseDialog handles:
  - window setup (always-on-top, centered)
  - countdown chip + auto-timeout
  - user_note expander
  - Cancel/Submit buttons + Esc/Ctrl+Enter shortcuts
  - on_done callback wiring
"""
from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from ..queue import Request
from .. import theme


class BaseDialog:
    submit_label = "Submit"
    cancel_label = "Cancel"
    minimum_width = theme.DEFAULT_WIDTH

    def __init__(self, root: ctk.CTk, req: Request,
                 on_done: Callable[[str, Any, str], None], logger) -> None:
        self.root = root
        self.req = req
        self.on_done = on_done
        self.log = logger
        self._closed = False
        self._user_note_var = ctk.StringVar(value="")
        self._timer_after_id: str | None = None
        self._countdown_after_id: str | None = None
        self._remaining = req.timeout_sec

        self.window = ctk.CTkToplevel(root)
        self.window.title(f"{req.origin} · {req.type}")
        self.window.attributes("-topmost", True)
        self.window.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.window.minsize(self.minimum_width, 180)
        self.window.bind("<Escape>", lambda _e: self._on_cancel())
        self.window.bind("<Control-Return>", lambda _e: self._on_submit())

        self._build_layout()
        self._center()
        self.window.lift()
        self.window.focus_force()
        self._start_countdown()

    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        # header
        header = ctk.CTkFrame(self.window, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 8))

        prompt = ctk.CTkLabel(
            header,
            text=self.req.prompt or "(no prompt)",
            font=theme.PROMPT_FONT,
            wraplength=self.minimum_width - 60,
            justify="left",
            anchor="w",
        )
        prompt.pack(fill="x", side="left", expand=True)

        self._countdown_chip = ctk.CTkLabel(
            header,
            text=self._format_remaining(),
            font=theme.SMALL_FONT,
            fg_color=("#dde", "#334"),
            corner_radius=8,
            padx=8,
            pady=2,
        )
        self._countdown_chip.pack(side="right", padx=(8, 0))

        # body — subclass-provided
        body = ctk.CTkFrame(self.window, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(4, 8))
        self._build_body(body)

        # user note expander
        note_frame = ctk.CTkFrame(self.window, fg_color="transparent")
        note_frame.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(
            note_frame, text="Add note (optional)", font=theme.SMALL_FONT, anchor="w"
        ).pack(fill="x")
        ctk.CTkEntry(
            note_frame,
            textvariable=self._user_note_var,
            placeholder_text="extra context for the model…",
        ).pack(fill="x", pady=(2, 0))

        # footer
        footer = ctk.CTkFrame(self.window, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(4, 14))

        ctk.CTkButton(
            footer, text=self.cancel_label, width=100,
            fg_color=("#bbb", "#444"), hover_color=("#aaa", "#555"),
            command=self._on_cancel,
        ).pack(side="left")
        self._submit_btn = ctk.CTkButton(
            footer, text=self.submit_label, width=120, command=self._on_submit
        )
        self._submit_btn.pack(side="right")

    def _build_body(self, parent: ctk.CTkBaseClass) -> None:
        raise NotImplementedError

    def _collect_value(self) -> Any:
        raise NotImplementedError

    # ------------------------------------------------------------------
    def _center(self) -> None:
        self.window.update()
        w = max(self.window.winfo_reqwidth(), self.minimum_width)
        h = self.window.winfo_reqheight()
        sw = self.window.winfo_screenwidth()
        sh = self.window.winfo_screenheight()
        w = min(w, sw - 40)
        h = min(h, sh - 80)
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 3)
        self.window.geometry(f"{w}x{h}+{x}+{y}")
        self.window.minsize(self.minimum_width, min(180, h))

    def _format_remaining(self) -> str:
        m, s = divmod(max(0, int(self._remaining)), 60)
        return f"⏱ {m:d}:{s:02d}"

    def _start_countdown(self) -> None:
        self._tick_countdown()
        self._timer_after_id = self.window.after(
            self.req.timeout_sec * 1000, self._on_timeout
        )

    def _tick_countdown(self) -> None:
        if self._closed:
            return
        try:
            self._countdown_chip.configure(text=self._format_remaining())
        except Exception:
            return
        self._remaining -= 1
        if self._remaining < 0:
            return
        self._countdown_after_id = self.window.after(1000, self._tick_countdown)

    # ------------------------------------------------------------------
    def _finish(self, status: str, value: Any) -> None:
        if self._closed:
            return
        self._closed = True
        if self._timer_after_id:
            try:
                self.window.after_cancel(self._timer_after_id)
            except Exception:
                pass
        if self._countdown_after_id:
            try:
                self.window.after_cancel(self._countdown_after_id)
            except Exception:
                pass
        try:
            self.window.destroy()
        except Exception:
            pass
        self.on_done(status, value, self._user_note_var.get())

    def _on_submit(self) -> None:
        try:
            value = self._collect_value()
        except ValueError as exc:
            self.log.info("submit blocked: %s", exc)
            self._show_inline_error(str(exc))
            return
        self._finish("answered", value)

    def _on_cancel(self) -> None:
        self._finish("cancelled", None)

    def _on_deny(self) -> None:
        self._finish("denied", False)

    def _on_timeout(self) -> None:
        self.log.info("dialog timed out id=%s", self.req.request_id)
        self._finish("timed_out", None)

    def _show_inline_error(self, message: str) -> None:
        # Subclasses can override to display the error inline.
        try:
            from tkinter import messagebox
            messagebox.showerror("Invalid input", message, parent=self.window)
        except Exception:
            self.log.warning("inline error: %s", message)
