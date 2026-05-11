"""Composite form dialog. Each field is a labelled widget by type.

Supported field types: text, password, multiline, choice, multi_choice,
checkbox, number.
"""
from __future__ import annotations

from typing import Any

import customtkinter as ctk

from .base import BaseDialog
from .. import theme


class FormDialog(BaseDialog):
    minimum_width = 540

    def _build_body(self, parent: ctk.CTkBaseClass) -> None:
        spec = self.req.spec or {}
        self._fields: list[dict[str, Any]] = list(spec.get("fields") or [])
        self._widgets: dict[str, dict[str, Any]] = {}

        if spec.get("title"):
            self.window.title(f"{self.req.origin} · {spec['title']}")

        scroll = ctk.CTkScrollableFrame(parent, height=300)
        scroll.pack(fill="both", expand=True)

        for f in self._fields:
            name = str(f.get("name") or "")
            if not name:
                continue
            label = str(f.get("label") or name)
            ftype = str(f.get("type") or "text").lower()
            required = bool(f.get("required", False))
            default = f.get("default")
            options = f.get("options") or []

            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(
                row,
                text=f"{label}{' *' if required else ''}",
                font=theme.BODY_FONT,
                anchor="w",
            ).pack(fill="x")

            entry: Any
            var: Any
            if ftype in ("text", "password"):
                var = ctk.StringVar(value=str(default) if default is not None else "")
                entry = ctk.CTkEntry(
                    row, textvariable=var,
                    placeholder_text=str(f.get("placeholder") or ""),
                    show="*" if ftype == "password" else "",
                )
                entry.pack(fill="x", pady=(2, 0))
            elif ftype == "multiline":
                entry = ctk.CTkTextbox(row, height=80, wrap="word")
                entry.pack(fill="x", pady=(2, 0))
                if default is not None:
                    entry.insert("1.0", str(default))
                var = None
            elif ftype == "number":
                var = ctk.StringVar(value=str(default) if default is not None else "")
                entry = ctk.CTkEntry(row, textvariable=var)
                entry.pack(fill="x", pady=(2, 0))
            elif ftype == "checkbox":
                var = ctk.BooleanVar(value=bool(default))
                entry = ctk.CTkCheckBox(row, variable=var, text=str(f.get("checkbox_label") or ""))
                entry.pack(anchor="w", pady=(2, 0))
            elif ftype == "choice":
                norm = self._normalize_options(options)
                var = ctk.StringVar(value=str(default) if default is not None else "")
                values = [o["label"] for o in norm]
                entry = ctk.CTkOptionMenu(row, variable=var, values=values or ["(no options)"])
                entry.pack(fill="x", pady=(2, 0))
            elif ftype == "multi_choice":
                norm = self._normalize_options(options)
                var = []
                cb_box = ctk.CTkFrame(row, fg_color="transparent")
                cb_box.pack(fill="x")
                for opt in norm:
                    bv = ctk.BooleanVar(value=opt["value"] in (default or []))
                    cb = ctk.CTkCheckBox(cb_box, variable=bv, text=opt["label"])
                    cb.pack(anchor="w")
                    var.append((bv, opt))
                entry = cb_box
            else:
                # unknown type — fall back to text
                var = ctk.StringVar(value=str(default) if default is not None else "")
                entry = ctk.CTkEntry(row, textvariable=var)
                entry.pack(fill="x", pady=(2, 0))

            self._widgets[name] = {
                "type": ftype,
                "required": required,
                "var": var,
                "entry": entry,
                "options": options,
            }

    def _normalize_options(self, options: list[Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for opt in options or []:
            if isinstance(opt, str):
                out.append({"label": opt, "value": opt})
            elif isinstance(opt, dict):
                lab = str(opt.get("label") or opt.get("value") or "")
                val = opt.get("value", lab)
                out.append({"label": lab, "value": val})
        return out

    def _collect_value(self) -> Any:
        result: dict[str, Any] = {}
        missing: list[str] = []

        for name, w in self._widgets.items():
            ftype = w["type"]
            if ftype in ("text", "password"):
                v = w["var"].get()
            elif ftype == "multiline":
                v = w["entry"].get("1.0", "end").rstrip("\n")
            elif ftype == "number":
                raw = w["var"].get().strip()
                if raw == "":
                    v = None
                else:
                    try:
                        v = int(raw) if raw.lstrip("-").isdigit() else float(raw)
                    except ValueError:
                        raise ValueError(f"field {name!r} must be a number")
            elif ftype == "checkbox":
                v = bool(w["var"].get())
            elif ftype == "choice":
                norm = self._normalize_options(w["options"])
                label = w["var"].get()
                v = next((o["value"] for o in norm if o["label"] == label), label or None)
            elif ftype == "multi_choice":
                v = [o["value"] for bv, o in w["var"] if bv.get()]
            else:
                v = w["var"].get()

            if w["required"]:
                empty = (
                    v is None
                    or (isinstance(v, str) and v.strip() == "")
                    or (isinstance(v, list) and not v)
                )
                if empty:
                    missing.append(name)
            result[name] = v

        if missing:
            raise ValueError(f"required fields missing: {', '.join(missing)}")
        return result
