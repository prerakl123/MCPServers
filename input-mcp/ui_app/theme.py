"""customtkinter appearance configuration."""
from __future__ import annotations

import os

import customtkinter as ctk

DEFAULT_WIDTH = 480
TITLE_FONT = ("Segoe UI", 12, "bold")
PROMPT_FONT = ("Segoe UI", 11)
BODY_FONT = ("Segoe UI", 11)
SMALL_FONT = ("Segoe UI", 9)


def configure() -> None:
    appearance = os.environ.get("INPUT_MCP_THEME", "system").lower()
    if appearance in ("light", "dark", "system"):
        ctk.set_appearance_mode(appearance)
    ctk.set_default_color_theme("blue")
