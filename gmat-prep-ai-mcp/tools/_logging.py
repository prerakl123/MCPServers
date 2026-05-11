"""File-based logger.

The MCP stdio transport uses stdout for the JSON-RPC protocol and stderr
for LM Studio's developer log. We additionally write our own log file at
``logs/mcp.log`` so we can debug tool behaviour without depending on LM
Studio's UI. This module is imported at the very top of ``main.py`` so any
crash during import is captured.
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOGGER_NAME = "gmat_mcp"
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s %(message)s"
_DEFAULT_LEVEL = "info"


def _resolve_level() -> int:
    raw = os.environ.get("GMAT_MCP_LOG_LEVEL", _DEFAULT_LEVEL).lower()
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
    """Return a logger configured against ``logs/mcp.log`` + stderr."""
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

        # stderr is consumed by LM Studio's developer log. Helpful for
        # surfacing crashes during stdio handshake.
        sh = logging.StreamHandler(stream=sys.stderr)
        sh.setFormatter(logging.Formatter(_FORMAT))
        base.addHandler(sh)
        base.propagate = False

    if name:
        return base.getChild(name)
    return base
