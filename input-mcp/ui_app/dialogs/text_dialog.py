"""Free-form text input dialog (single-line or multiline)."""
from __future__ import annotations

import re
from typing import Any

import customtkinter as ctk

from .base import BaseDialog


class TextDialog(BaseDialog):
    def _build_body(self, parent: ctk.CTkBaseClass) -> None:
        spec = self.req.spec or {}
        self._multiline = bool(spec.get("multiline", False))
        self._regex = spec.get("regex_validate")
        default = str(spec.get("default") or "")
        placeholder = str(spec.get("placeholder") or "")

        if self._multiline:
            self._text = ctk.CTkTextbox(parent, height=140, wrap="word")
            self._text.pack(fill="both", expand=True)
            if default:
                self._text.insert("1.0", default)
            self._text.focus_set()
        else:
            self._var = ctk.StringVar(value=default)
            self._entry = ctk.CTkEntry(
                parent, textvariable=self._var, placeholder_text=placeholder
            )
            self._entry.pack(fill="x")
            self._entry.bind("<Return>", lambda _e: self._on_submit())
            self._entry.focus_set()
            self._entry.icursor("end")

    def _collect_value(self) -> Any:
        if self._multiline:
            value = self._text.get("1.0", "end").rstrip("\n")
        else:
            value = self._var.get()
        if self._regex:
            try:
                if not re.fullmatch(self._regex, value):
                    raise ValueError(f"input does not match {self._regex!r}")
            except re.error as exc:
                self.log.warning("invalid regex_validate %r: %s", self._regex, exc)
        return value
