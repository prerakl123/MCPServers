"""Single- or multi-select choice dialog with optional 'Other' free-text."""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from .base import BaseDialog
from .. import theme


class ChoiceDialog(BaseDialog):
    minimum_width = 520

    def _build_body(self, parent: ctk.CTkBaseClass) -> None:
        spec = self.req.spec or {}
        raw_options = spec.get("options") or []
        self._multi = bool(spec.get("multi_select", False))
        self._allow_other = bool(spec.get("allow_other", True))

        # Normalize options into [{label, value, description}]
        self._options: list[dict[str, Any]] = []
        for i, opt in enumerate(raw_options):
            if isinstance(opt, str):
                self._options.append({"label": opt, "value": opt, "description": ""})
            elif isinstance(opt, dict):
                label = str(opt.get("label") or opt.get("value") or f"Option {i+1}")
                value = opt.get("value", label)
                self._options.append({
                    "label": label,
                    "value": value,
                    "description": str(opt.get("description") or ""),
                })

        scroll = ctk.CTkScrollableFrame(parent, height=240)
        scroll.pack(fill="both", expand=True)

        self._vars: list[Any] = []
        self._radio_var = ctk.StringVar(value="")

        for i, opt in enumerate(self._options):
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)
            if self._multi:
                v = ctk.BooleanVar(value=False)
                cb = ctk.CTkCheckBox(row, variable=v, text=opt["label"])
                cb.pack(side="left", anchor="w")
                self._vars.append(v)
            else:
                rb = ctk.CTkRadioButton(
                    row, variable=self._radio_var,
                    value=str(i), text=opt["label"],
                )
                rb.pack(side="left", anchor="w")
                self._vars.append(rb)
            if opt["description"]:
                ctk.CTkLabel(
                    row, text=opt["description"], font=theme.SMALL_FONT,
                    text_color=("#555", "#aaa"), anchor="w",
                ).pack(side="left", padx=(10, 0), fill="x", expand=True)

        # Other option
        self._other_var = ctk.StringVar(value="")
        if self._allow_other:
            other_row = ctk.CTkFrame(parent, fg_color="transparent")
            other_row.pack(fill="x", pady=(8, 0))
            ctk.CTkLabel(other_row, text="Other:", font=theme.BODY_FONT).pack(side="left")
            ctk.CTkEntry(
                other_row, textvariable=self._other_var,
                placeholder_text="custom value (optional)",
            ).pack(side="left", fill="x", expand=True, padx=(8, 0))

    def _collect_value(self) -> Any:
        other = self._other_var.get().strip() if self._allow_other else ""

        if self._multi:
            picked = [
                self._options[i]["value"]
                for i, var in enumerate(self._vars)
                if var.get()
            ]
            if other:
                picked.append(other)
            if not picked:
                raise ValueError("select at least one option (or fill Other)")
            return picked

        idx_str = self._radio_var.get()
        if idx_str == "" and not other:
            raise ValueError("pick an option (or fill Other)")
        if other and idx_str == "":
            return other
        return self._options[int(idx_str)]["value"]
