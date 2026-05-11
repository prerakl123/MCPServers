"""File-based logger for both the MCP server and the UI app.

Two distinct log files:
- logs/mcp.log  (server side)
- logs/ui.log   (ui_app side)

The UI app passes `name='ui'` to direct its records to ui.log; everything
else lands in mcp.log.
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s %(message)s"
_DEFAULT_LEVEL = "info"


def _resolve_level() -> int:
    raw = os.environ.get("INPUT_MCP_LOG_LEVEL", _DEFAULT_LEVEL).lower()
    return {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "warn": logging.WARNING,
        "error": logging.ERROR,
    }.get(raw, logging.INFO)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _build_logger(logger_name: str, file_name: str) -> logging.Logger:
    base = logging.getLogger(logger_name)
    if base.handlers:
        return base
    base.setLevel(_resolve_level())

    log_dir = _project_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    fh = RotatingFileHandler(
        log_dir / file_name,
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setFormatter(logging.Formatter(_FORMAT))
    base.addHandler(fh)

    sh = logging.StreamHandler(stream=sys.stderr)
    sh.setFormatter(logging.Formatter(_FORMAT))
    base.addHandler(sh)
    base.propagate = False
    return base


def get_logger(name: str | None = None) -> logging.Logger:
    base = _build_logger("input_mcp", "mcp.log")
    return base.getChild(name) if name else base


def get_ui_logger(name: str | None = None) -> logging.Logger:
    base = _build_logger("input_mcp_ui", "ui.log")
    return base.getChild(name) if name else base