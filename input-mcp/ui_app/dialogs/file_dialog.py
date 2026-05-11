"""File / directory picker. Wraps tkinter.filedialog.

We still display a small dialog window so the user sees the prompt and the
'Add note' field; the OS-native picker fires when the user clicks Browse.
"""
from __future__ import annotations

from tkinter import filedialog
from typing import Any

import customtkinter as ctk

from .base import BaseDialog
from .. import theme


class FileDialog(BaseDialog):
    minimum_width = 540

    def _build_body(self, parent: ctk.CTkBaseClass) -> None:
        spec = self.req.spec or {}
        self._mode = str(spec.get("mode") or "open").lower()
        self._multiple = bool(spec.get("multiple", False))
        self._filters = spec.get("filters") or []  # [{name, patterns}]

        self._selection: list[str] | str | None = None
        self._var = ctk.StringVar(value="")

        ctk.CTkLabel(
            parent, text="Click Browse to choose a file/directory.",
            anchor="w", justify="left", font=theme.SMALL_FONT,
        ).pack(fill="x", anchor="w")

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(6, 0))
        ctk.CTkEntry(
            row, textvariable=self._var, placeholder_text="(no selection)",
            state="disabled",
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            row, text="Browse…", width=100, command=self._on_browse,
        ).pack(side="left", padx=(8, 0))

    def _on_browse(self) -> None:
        prompt = self.req.prompt or "Select file"
        types = self._build_filetypes()
        try:
            if self._mode == "directory":
                path = filedialog.askdirectory(parent=self.window, title=prompt)
                self._selection = path or None
            elif self._mode == "save":
                path = filedialog.asksaveasfilename(
                    parent=self.window, title=prompt, filetypes=types
                )
                self._selection = path or None
            else:  # open
                if self._multiple:
                    paths = filedialog.askopenfilenames(
                        parent=self.window, title=prompt, filetypes=types
                    )
                    self._selection = list(paths) if paths else None
                else:
                    path = filedialog.askopenfilename(
                        parent=self.window, title=prompt, filetypes=types
                    )
                    self._selection = path or None
        except Exception as exc:  # noqa: BLE001
            self.log.warning("file picker failed: %s", exc)
            self._selection = None

        if self._selection is None:
            self._var.set("")
        elif isinstance(self._selection, list):
            self._var.set(f"{len(self._selection)} files selected")
        else:
            self._var.set(self._selection)

        # Re-focus our window so user can submit/cancel.
        self.window.lift()
        self.window.focus_force()

    def _build_filetypes(self) -> list[tuple[str, str]]:
        ftypes: list[tuple[str, str]] = []
        for f in self._filters or []:
            try:
                name = str(f.get("name") or "files")
                patterns = f.get("patterns") or ["*"]
                if isinstance(patterns, list):
                    patterns = " ".join(patterns)
                ftypes.append((name, patterns))
            except Exception:
                continue
        if not ftypes:
            ftypes = [("All files", "*.*")]
        return ftypes

    def _collect_value(self) -> Any:
        if self._selection is None:
            raise ValueError("no file selected — click Browse first or Cancel")
        return self._selection
