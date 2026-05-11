"""Yes/No confirmation dialog. The deny button issues status='denied'."""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from .base import BaseDialog


class ConfirmDialog(BaseDialog):
    minimum_width = 460

    def _build_body(self, parent: ctk.CTkBaseClass) -> None:
        spec = self.req.spec or {}
        self.submit_label = str(spec.get("confirm_label") or "Yes")
        self._deny_label = str(spec.get("deny_label") or "No")
        self._default = (spec.get("default") or "").lower() if spec.get("default") else None

        # ConfirmDialog does NOT use the default Submit button; we replace
        # the footer with explicit Confirm/Deny buttons by overriding here.
        # But base already built footer — we'll build an additional row.
        # Simpler: override _build_layout? Easier to add a hint here and
        # override _on_submit.
        ctk.CTkLabel(
            parent,
            text="Click Confirm to accept, Deny to refuse, or Cancel to dismiss.",
            anchor="w",
            justify="left",
        ).pack(fill="x", anchor="w")

    def _build_layout(self) -> None:
        super()._build_layout()
        # Override the default Submit button label/behaviour and add Deny.
        # The base class stored the submit button as self._submit_btn.
        # Insert a Deny button between Cancel and Submit.
        self._submit_btn.configure(text=self.submit_label)
        deny_btn = ctk.CTkButton(
            self._submit_btn.master,
            text=self._deny_label,
            width=100,
            fg_color=("#d97766", "#7a3a30"),
            hover_color=("#c8624f", "#682f25"),
            command=self._on_deny,
        )
        deny_btn.pack(side="right", padx=(0, 8))

        # Apply default focus (Y/N keys submit/deny)
        self.window.bind("y", lambda _e: self._on_submit())
        self.window.bind("Y", lambda _e: self._on_submit())
        self.window.bind("n", lambda _e: self._on_deny())
        self.window.bind("N", lambda _e: self._on_deny())

        if self._default == "yes":
            self._submit_btn.focus_set()
        elif self._default == "no":
            deny_btn.focus_set()

    def _collect_value(self) -> Any:
        return True
