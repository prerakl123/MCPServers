"""File-based logger shared across tool modules."""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOGGER_NAME = "kg_mcp"
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s %(message)s"
_DEFAULT_LEVEL = "info"


def _resolve_level() -> int:
    raw = os.environ.get("KG_MCP_LOG_LEVEL", _DEFAULT_LEVEL).lower()
    return {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "warn": logging.WARNING,
        "error": logging.ERROR,
    }.get(raw, logging.INFO)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_logger(name: str | None = None) -> logging.Logger:
    base = logging.getLogger(_LOGGER_NAME)
    if not base.handlers:
        base.setLevel(_resolve_level())
        log_dir = _project_root() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        fh = RotatingFileHandler(
            log_dir / "mcp.log",
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

    return base.getChild(name) if name else base